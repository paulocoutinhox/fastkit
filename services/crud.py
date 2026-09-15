from dataclasses import dataclass, field
from typing import Callable

from pydantic.alias_generators import to_camel
from sqlalchemy import String, case, cast, func, literal, or_, select
from sqlalchemy import delete as sql_delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from enums.upload import UploadPurpose
from enums.user import UserRole
from helpers.db import Base, commit, refusing
from helpers.errors import ConflictError, NotFoundError, ValidationError
from helpers.pagination import PageParams
from helpers.scope import belongs_to_tenant, reaches_tenant
from helpers.search import TextMatch, TextRank, contains, phrase_of, tokens_of
from helpers.settings import settings
from helpers.text import alphabetical, slugify
from models.language import Language
from services.upload import named_in, owner_of, upload_service


def settled_key(key: str) -> bool:
    """Whether a key stays where it says it is, which nothing that climbs, doubles back or starts at the root ever does."""
    return ".." not in key and "\\" not in key and not key.startswith("/") and "//" not in key


@dataclass(frozen=True)
class Elsewhere:
    """A filter whose column lives on another table: the column is what the value is read through, and the condition is what it narrows the listing to."""

    column: object
    narrows: Callable


def services_by_model() -> dict:
    """Every service by the model it serves, walked to the bottom of the tree because a resource that gained a base of its own is invisible to one level of it."""
    # The tree is walked on every call: kept, the first caller would freeze the map with whatever happened to be imported by then, and a service loaded later would be missing from it for the life of the process.
    found = {}
    pending = [CrudService]

    while pending:
        current = pending.pop()
        pending.extend(current.__subclasses__())

        if getattr(current, "model", None) is not None:
            found.setdefault(current.model, current())

    return found


def roles_storing(purpose: UploadPurpose) -> set[UserRole]:
    """Who may put a file of this purpose into storage, which is whoever may write a record that keeps one: a file column of that purpose, or markup, where the editor embeds an image."""
    return {role for service in services_by_model().values() if purpose in service.file_fields.values() or (purpose == UploadPurpose.IMAGE and service.markup_fields) for role in service.roles}


def referenced(model) -> dict:
    """Every column of a model that points at another row, by the model it points at."""
    tables = {mapper.class_.__table__: mapper.class_ for mapper in Base.registry.mappers}

    return {column.name: tables[key.column.table] for column in model.__table__.columns for key in column.foreign_keys if key.column.table in tables}


@dataclass(frozen=True)
class Reach:
    """How a resource with no tenant of its own is confined, which is always the row it belongs to: the key it points with, the model it points at, and how that one reaches a tenant when it carries none either."""

    column: object
    parent: type
    through: "Reach | None" = None


@dataclass(frozen=True)
class Dependent:
    """A table that must go before its parent."""

    model: type
    field: str
    dependents: tuple["Dependent", ...] = field(default_factory=tuple)


# What keeps the pages of the site current, which is the one thing a role short of an administrator is given here.
EDITING = (UserRole.ADMINISTRATOR, UserRole.EDITOR)


class CrudService:
    """The read and write path shared by every admin resource, which a module subclasses to declare what it owns."""

    model: type = None
    search_fields: tuple[str, ...] = ()
    text_search_fields: tuple[str, ...] = ()
    filter_fields: tuple[str, ...] = ()

    # The filters of this resource that name something of another table, which is the one thing a subclass says about them.
    filters_elsewhere: dict[str, Elsewhere] = {}

    ordering_fields: tuple[str, ...] = ("id",)
    default_ordering: str = "-id"
    relations: tuple[str, ...] = ()
    label_fields: tuple[str, ...] = ("name",)
    # Who reaches this resource through the API, which is the one line that decides it.
    roles: tuple[UserRole, ...] = (UserRole.ADMINISTRATOR,)

    # Who may resolve it as an option of somebody else's form, which a catalogue widens because a form nobody can fill is a form nobody can send.
    lookup_roles: tuple[UserRole, ...] = ()
    # Every file column with the purpose it belongs to, which is what says both where the key may point and what to delete.
    file_fields: dict[str, UploadPurpose] = {}
    markup_fields: tuple[str, ...] = ()
    dependents: tuple[Dependent, ...] = ()
    position_field: str | None = None

    # How this resource is confined when it carries no tenant of its own, because a child is confined by its parent and never by a column somebody added to it.
    reaches_through: Reach | None = None

    # A catalogue of the system, which belongs to no brand and is therefore managed only by an operator that belongs to none either.
    system_wide: bool = False

    # A row of no brand is a catalogue every brand shares only where the resource says so, because an account, what it bought and what the system recorded belong to the instance and to no brand.
    shared: bool = False

    def confinement(self, operator, writing: bool = False):
        """What narrows a statement to the operator asking for it, which is nothing at all when that operator belongs to no tenant."""
        # A catalogue of the system is refused whole rather than narrowed, which is a different thing and settled elsewhere.
        if operator is None or operator.tenant_id is None or self.system_wide:
            return None

        # Reaching the shared rows is reading them, and writing one would let a brand rewrite what every other brand reads.
        scoped = reaches_tenant if operator.reaches_shared and self.shared and not writing else belongs_to_tenant

        def wanted(column):
            return scoped(column, operator.tenant_id)

        if "tenant_id" in self.model.__table__.columns:
            return wanted(self.model.tenant_id)

        return self.through(self.reaches_through, wanted)

    def through(self, reach: Reach, wanted):
        """A child is confined by the row it belongs to, and one whose parent carries no tenant either is confined by whatever that parent belongs to."""
        held = wanted(reach.parent.tenant_id) if "tenant_id" in reach.parent.__table__.columns else self.through(reach.through, wanted)

        return reach.column.in_(select(reach.parent.id).where(held))

    def confine(self, statement, operator, writing: bool = False):
        narrowed = self.confinement(operator, writing)

        return statement if narrowed is None else statement.where(narrowed)

    def load_option(self, path: str):
        """A relation is named by its path, so `subcategory.category` loads both levels in one go."""
        model = self.model
        option = None

        for name in path.split("."):
            attribute = getattr(model, name)
            option = selectinload(attribute) if option is None else option.selectinload(attribute)
            model = attribute.property.mapper.class_

        return option

    def base_statement(self):
        statement = select(self.model)

        for relation in self.relations:
            statement = statement.options(self.load_option(relation))

        return statement

    def text_columns(self):
        return [getattr(self.model, name) for name in self.text_search_fields]

    def apply_search(self, statement, search: str | None):
        """Prose answers a word from its start and an identifier answers a piece of itself, because nobody remembers half of a name but everybody remembers the middle of a document number."""
        term = (search or "").strip()

        if not term:
            return statement

        conditions = [contains(getattr(self.model, name), term) for name in self.search_fields]
        tokens = tokens_of(term)

        if self.text_search_fields and tokens:
            conditions.append(TextMatch(self.text_columns(), tokens))

        if not conditions:
            return statement

        return statement.where(or_(*conditions))

    def search_ordering(self, search: str | None, ordering: str | None):
        """The phrase as it was typed outranks the words it was cut into, and an order the client asked for outranks both."""
        phrase = phrase_of(search or "")

        if ordering or not phrase or not self.text_search_fields:
            return []

        return [TextRank(self.text_columns(), phrase).desc()]

    def filter_column(self, name: str):
        """The column a filter is read through, which is one of this table unless the resource declared it lives on another."""
        elsewhere = self.filters_elsewhere.get(name)

        return elsewhere.column if elsewhere else getattr(self.model, name)

    def apply_filters(self, statement, filters: dict):
        for name, value in filters.items():
            if name not in self.filter_fields or value is None:
                continue

            elsewhere = self.filters_elsewhere.get(name)
            statement = statement.where(elsewhere.narrows(value) if elsewhere else getattr(self.model, name) == value)

        return statement

    def apply_ordering(self, statement, ordering: str | None, search: str | None = None):
        """The client names a column the way the API spells it, and the minus that reverses it is not part of the name."""
        expression = ordering or self.default_ordering
        descending = expression.startswith("-")
        # The name is read the way a filter is, because turning camelCase back loses the digits of a column like code_iso_639_1.
        name = expression.lstrip("-") if ordering is None else {to_camel(field): field for field in self.ordering_fields}.get(ordering.lstrip("-"))

        # Answering a different order than the one that was asked for is a lie the caller cannot see.
        if name not in self.ordering_fields:
            raise ValidationError("error.ordering-not-allowed", "ordering")

        column = getattr(self.model, name)
        direction = column.desc() if descending else column.asc()

        # The key breaks every tie, or two rows sharing a position land on two pages and a third lands on none.
        settled = self.model.id.desc() if descending else self.model.id.asc()

        return statement.order_by(*self.search_ordering(search, ordering), direction, settled)

    async def paginate(self, db: AsyncSession, page: PageParams, filters: dict | None = None, operator=None) -> tuple[int, list]:
        statement = self.confine(self.apply_filters(self.apply_search(self.base_statement(), page.search), filters or {}), operator)

        total = await db.scalar(select(func.count()).select_from(statement.order_by(None).subquery()))

        statement = self.apply_ordering(statement, page.ordering, page.search).limit(page.limit).offset(page.offset)
        result = await db.execute(statement)

        return total, list(result.scalars().unique())

    async def find(self, db: AsyncSession, record_id: int, operator=None, writing: bool = False):
        # A row already in the session keeps the relations it was loaded with, so an edit that moved a key would answer the row it pointed at before.
        result = await db.execute(self.confine(self.base_statement(), operator, writing).where(self.model.id == record_id).execution_options(populate_existing=True))

        return result.scalars().unique().one_or_none()

    async def get(self, db: AsyncSession, record_id: int, operator=None, writing: bool = False):
        instance = await self.find(db, record_id, operator, writing)

        if instance is None:
            raise NotFoundError()

        return instance

    def label_ordering(self):
        """A lookup answers with the alphabetically first rows, so the limit cuts the tail of the list and not an arbitrary slice."""
        # A column with no value is last in every dialect, said as a predicate because MySQL reads a null as the smallest and PostgreSQL as the largest.
        return [expression for name in self.label_fields for expression in (getattr(self.model, name).is_(None), getattr(self.model, name).asc())] + [self.model.id.asc()]

    async def lookup(self, db: AsyncSession, search: str | None, limit: int, filters: dict | None = None, operator=None) -> list[dict]:
        statement = self.confine(self.apply_filters(self.apply_search(self.base_statement(), search), filters or {}), operator)
        statement = statement.order_by(*self.label_ordering()).limit(limit)
        result = await db.execute(statement)

        options = [{"id": instance.id, "label": self.build_label(instance)} for instance in result.scalars().unique()]

        return sorted(options, key=lambda option: alphabetical(option["label"]))

    def build_label(self, instance) -> str:
        parts = [str(getattr(instance, name)) for name in self.label_fields if getattr(instance, name, None)]

        return " - ".join(parts) or f"#{instance.id}"

    def ensure_files_are_of_their_purpose(self, data: dict) -> None:
        """A file column is the target of the next deletion, so a key of another folder would erase a cover, an asset or a banner on the following save."""
        for name, purpose in self.file_fields.items():
            key = str(data.get(name) or "")

            if not key:
                continue

            # The folder alone is not enough: `images/product/../../secret` begins with it and names something else entirely.
            if not key.startswith(f"{upload_service.rule_for(purpose).folder}/") or not settled_key(key):
                raise ValidationError("error.upload-key-out-of-purpose", name)

    async def ensure_references_are_reachable(self, db: AsyncSession, data: dict, operator, instance=None) -> None:
        """A key naming no row, or a row the panel would never have offered, is refused here: left to the flush it reads as a duplicate, and a hook reading the parent meets nothing."""
        # A child is written inside the row it belongs to, so its parent has to be one this operator may write, while any other key only points at a row it may read.
        parent = self.reaches_through.column.key if self.reaches_through else None

        for name, target in referenced(self.model).items():
            if name not in data or data[name] is None:
                continue

            # A key the edit leaves as it was is not this operator's choice, and a brand's page under a shared category an operator of no brand wrote would otherwise never be saved again by the brand.
            if instance is not None and data[name] == getattr(instance, name):
                continue

            statement = select(target.id).where(target.id == data[name])
            narrowed = services_by_model()[target].confinement(operator, writing=name == parent)

            if await db.scalar(statement if narrowed is None else statement.where(narrowed)) is None:
                raise ValidationError("error.related-not-found", name)

    async def ensure_referrers_still_reach(self, db: AsyncSession, data: dict, instance) -> None:
        """A row moved into one brand leaves every row of another that points at it pointing across brands, so the move waits until nothing points at it."""
        if "tenant_id" not in self.model.__table__.columns or data.get("tenant_id", instance.tenant_id) in (None, instance.tenant_id):
            return

        for model in (mapper.class_ for mapper in Base.registry.mappers):
            for name, target in referenced(model).items():
                if target is self.model and await db.scalar(select(model.__table__.c[name]).where(model.__table__.c[name] == instance.id).limit(1)) is not None:
                    raise ValidationError("error.record-still-referenced", "tenant_id")

    async def ensure_children_stay_shared(self, db: AsyncSession, data: dict, instance) -> None:
        """A row moved into every brand carries its children along, so one of them still pointing at a row of a single brand would hand that row to every brand."""
        if "tenant_id" not in self.model.__table__.columns or instance.tenant_id is None or data.get("tenant_id", instance.tenant_id) is not None:
            return

        for child in services_by_model().values():
            reach = child.reaches_through

            if reach is None or reach.parent is not self.model:
                continue

            for name, target in referenced(child.model).items():
                if name == reach.column.key or "tenant_id" not in target.__table__.columns:
                    continue

                branded = select(target.id).where(target.tenant_id.is_not(None))

                if await db.scalar(select(child.model.id).where(reach.column == instance.id, child.model.__table__.c[name].in_(branded)).limit(1)) is not None:
                    raise ValidationError("error.children-of-a-brand", "tenant_id")

    def stamped(self, data: dict, operator) -> dict:
        """What an operator of one brand writes belongs to that brand, so the row is stamped here and never named in the payload."""
        if operator is None or operator.tenant_id is None or "tenant_id" not in self.model.__table__.columns:
            return data

        return {**data, "tenant_id": operator.tenant_id}

    async def create(self, db: AsyncSession, data: dict, operator=None):
        stamped = self.stamped(data, operator)

        await self.ensure_references_are_reachable(db, stamped, operator)
        self.ensure_files_are_of_their_purpose(stamped)
        await self.validate(db, stamped, None)

        prepared = await self.prepare(stamped, None)
        instance = self.model(**prepared)

        db.add(instance)

        # The row needs its id before it can be written down as naming a file, and a key refused while it is given one is the same conflict as at the commit.
        async with refusing(db, "error.duplicated-record"):
            await db.flush()

        await upload_service.mention(db, owner_of(instance), self.mentioned(instance), self.keys_of(instance))
        await self.persist(db)
        await self.after_save(db, instance, None)

        return await self.get(db, instance.id, operator)

    async def update(self, db: AsyncSession, record_id: int, data: dict, operator=None):
        instance = await self.get(db, record_id, operator, writing=True)
        stamped = self.stamped(data, operator)

        await self.ensure_references_are_reachable(db, stamped, operator, instance)
        await self.ensure_referrers_still_reach(db, stamped, instance)
        await self.ensure_children_stay_shared(db, stamped, instance)
        self.ensure_files_are_of_their_purpose(stamped)
        await self.validate(db, stamped, instance)

        previous = {name: getattr(instance, name) for name in self.file_fields}
        mentioned = self.mentioned(instance)

        prepared = await self.prepare(stamped, instance)

        for name, value in prepared.items():
            setattr(instance, name, value)

        # A key refused while the edit is written is the same conflict as at the commit, and the mentions below open a savepoint that would flush it outside that translation.
        async with refusing(db, "error.duplicated-record"):
            await db.flush()

        dropped = await upload_service.mention(db, owner_of(instance), self.mentioned(instance), self.keys_of(instance))
        await self.persist(db)
        await self.after_save(db, instance, previous)

        # A file goes only once the row stopped naming it, or a write that never landed would leave the record naming what is gone.
        # What another edit of the same row named in between is only in what was written down, so both are candidates.
        await upload_service.release(db, (mentioned - self.mentioned(instance)) | dropped)

        return await self.get(db, instance.id, operator)

    async def delete(self, db: AsyncSession, record_id: int, operator=None) -> None:
        instance = await self.get(db, record_id, operator, writing=True)

        await self.before_delete(db, instance)

        orphaned = self.mentioned(instance) | await upload_service.forget(db, [owner_of(instance)])

        # A key refused on the way out is a row something still points at, and the statement it refuses is often a child of this one rather than the commit.
        async with refusing(db, "error.record-still-referenced"):
            orphaned |= await self.delete_dependents(db, self.dependents, [record_id])

            await db.delete(instance)
            await db.commit()

        # The file goes only once the row that named it is gone, because a refused deletion would otherwise leave a record pointing at nothing.
        await upload_service.release(db, orphaned)

    async def reorder(self, db: AsyncSession, ids: list[int], operator=None) -> list:
        """The order the operator dragged into place, written in one go."""
        column = getattr(self.model, self.position_field)
        rows = {row.id: row for row in (await db.execute(self.confine(select(self.model), operator, writing=True).where(self.model.id.in_(ids)))).scalars()}

        if len(rows) != len(ids):
            raise NotFoundError()

        for index, record_id in enumerate(ids):
            setattr(rows[record_id], self.position_field, index)

        await self.persist(db)

        return list((await db.execute(self.base_statement().where(self.model.id.in_(ids)).order_by(column.asc(), self.model.id.asc()))).scalars().unique())

    async def delete_dependents(self, db: AsyncSession, dependents: tuple[Dependent, ...], parents) -> set[str]:
        """Children go first, deepest branch first, and every file they named is answered so it can go once the rows are gone."""
        orphaned = set()

        for dependent in dependents:
            column = getattr(dependent.model, dependent.field)

            # The rows are named by a subquery and never loaded, because a tenant's log is millions of lines and what they named is already written down beside them.
            if dependent.dependents:
                orphaned |= await self.delete_dependents(db, dependent.dependents, select(dependent.model.id).where(column.in_(parents)))

            if services_by_model()[dependent.model].mentions():
                orphaned |= await upload_service.forget(db, select(literal(f"{dependent.model.__tablename__}:") + cast(dependent.model.id, String)).where(column.in_(parents)))

            await db.execute(sql_delete(dependent.model).where(column.in_(parents)))

        return orphaned

    def mentions(self) -> tuple[str, ...]:
        """The columns a stored file can be named in: a key of its own, a link the editor wrote inside markup, and the free-form map an operator fills by hand."""
        return tuple(self.file_fields) + self.markup_fields + (("meta",) if hasattr(self.model, "meta") else ())

    def keys_of(self, instance) -> list[str]:
        """The storage keys the file columns of a row hold, which are files by what the column is and not by what a value looks like."""
        return [value for name in self.file_fields if (value := getattr(instance, name, None))]

    def mentioned(self, instance) -> set[str]:
        return named_in([getattr(instance, name, None) for name in self.mentions()])

    async def persist(self, db: AsyncSession) -> None:
        await commit(db)

    async def prepare(self, data: dict, instance) -> dict:
        return data

    async def validate(self, db: AsyncSession, data: dict, instance) -> None:
        return None

    async def after_save(self, db: AsyncSession, instance, previous: dict | None) -> None:
        return None

    async def before_delete(self, db: AsyncSession, instance) -> None:
        return None

    def column_length(self, name: str) -> int | None:
        return getattr(self.model.__table__.columns[name].type, "length", None)

    def column_default(self, name: str):
        default = self.model.__table__.columns[name].default

        return default.arg if default is not None and default.is_scalar else None

    def declared(self, prepared: dict, instance, name: str):
        """A create payload carries only what was set, so a value left out is the one the column defaults to."""
        if name in prepared:
            return prepared[name]

        if instance is not None:
            return getattr(instance, name)

        return self.column_default(name)

    def apply_slug(self, prepared: dict, instance, target: str, sources: tuple[str, ...], fallback: str) -> dict:
        """The value this record is addressed by, which is a slug whether somebody typed it or it was derived from the first source carrying one."""
        # An edit that does not mention the column leaves the record answering by whatever it already answers by.
        if instance is not None and target not in prepared:
            return prepared

        derived = next((value for name in sources if (value := prepared.get(name) or getattr(instance, name, None))), None)
        chosen = prepared.get(target) or derived

        if not chosen:
            prepared[target] = fallback

            return prepared

        # A typed value reaches an address, a storage key and a template folder exactly as it was written, so it is cut to a slug like a derived one.
        prepared[target] = slugify(str(chosen), fallback, self.column_length(target))

        return prepared

    async def ensure_reaches(self, db: AsyncSession, model, target_id: int | None, tenant_id: int | None, field_name: str, code: str = "error.related-not-found") -> None:
        """A row points only at what its own brand reaches, a row of that brand or a shared one: the form narrows the list, and this is the half that refuses what somebody sent anyway."""
        if target_id is None:
            return

        target = await db.get(model, target_id)

        if target is None or target.tenant_id not in (None, tenant_id):
            raise ValidationError(code, field_name)

    async def ensure_unique(self, db: AsyncSession, column, value, code: str, field_name: str, instance, scope=None) -> None:
        """A value is unique inside whatever the resource says its scope is, and by default that is the whole table."""
        if value is None or value == "":
            return

        statement = select(self.model.id).where(column == value)

        if scope is not None:
            statement = statement.where(scope)

        if instance is not None:
            statement = statement.where(self.model.id != instance.id)

        if await db.scalar(statement) is not None:
            raise ConflictError(code, field_name)


class LocalizedService(CrudService):
    """A resource written once per language, where the language a page is read in decides which of the rows answers for it."""

    # The column naming the same thing across its languages, which is what exactly one row is answered per.
    localized_key: str = ""

    def language_ranking(self, language: str | None):
        """The language asked for wins, the default language of the instance answers when it is missing, and anything published answers before nothing does."""
        wanted = [(Language.code_iso_639_1 == language, 0)] if language else []

        return case(*wanted, (Language.code_iso_639_1 == settings.default_language, len(wanted)), else_=len(wanted) + 1)

    def by_language(self, statement, language: str | None):
        # The shared row is the one carrying no tenant, said as a predicate because PostgreSQL sorts a null above every value and the other two below.
        return statement.outerjoin(Language, Language.id == self.model.language_id).order_by(self.language_ranking(language).asc(), self.model.tenant_id.is_(None), self.model.id.asc())

    def one_per_key(self, rows, ordering: tuple[str, ...]) -> list:
        """One row per key, and the very one that key opens: a card that shows a title and opens another is worse than no card."""
        picked: dict = {}

        for row in rows:
            picked.setdefault(getattr(row, self.localized_key), row)

        return sorted(picked.values(), key=lambda row: tuple(getattr(row, name) for name in ordering))


class TaggedService(LocalizedService):
    """A resource a page reaches by its tag, answering in the language that page is written in."""

    localized_key = "tag"
    listing_fields: tuple[str, ...] = ("id",)

    def reachable(self, tenant_id: int | None):
        return self.base_statement().where(self.model.active.is_(True), reaches_tenant(self.model.tenant_id, tenant_id))

    async def find_by_tag(self, db: AsyncSession, tag: str, tenant_id: int | None, language: str | None = None):
        """A tenant sees its own version of a tag first and the shared one only when it has none."""
        return await db.scalar(self.by_language(self.reachable(tenant_id).where(self.model.tag == tag), language))

    async def tags_that_answer(self, db: AsyncSession, wanted: tuple[str, ...], tenant_id: int | None, language: str | None = None) -> set[str]:
        """Which of these tags this brand answers, because a link to a page nobody wrote is a dead link on every page that draws it."""
        answered = (await db.execute(self.by_language(self.reachable(tenant_id).where(self.model.tag.in_(wanted)), language))).scalars().unique()

        return {row.tag for row in answered}

    async def list_reachable(self, db: AsyncSession, tenant_id: int | None, language: str | None = None) -> list:
        """One row per tag, in the order a listing draws them."""
        answered = (await db.execute(self.by_language(self.reachable(tenant_id), language))).scalars().unique()

        return self.one_per_key(answered, self.listing_fields)
