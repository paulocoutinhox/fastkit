from __future__ import annotations

from typing import Generic, TypeVar

from sqlalchemy import Integer, func, or_, select
from sqlalchemy.exc import IntegrityError

from fastkit_core.api.pagination import OffsetPage, clamp_page_size
from fastkit_core.errors.codes import (
    AUTHORIZATION_DENIED,
    CONFLICT_STATE,
    CONFLICT_UNIQUE,
    RESOURCE_NOT_FOUND,
    VALIDATION_FAILED,
)
from fastkit_core.errors.exceptions import (
    AuthorizationError,
    ConflictError,
    FastKitError,
    FieldError,
    NotFoundError,
    ValidationError,
)
from fastkit_db.integrity import classify_integrity_error
from fastkit_admin.columns import normalize_columns
from fastkit_admin.fields import PasswordField
from fastkit_admin.filters import Filter
from fastkit_admin.integrity import integrity_fields
from fastkit_admin.inlines import InlineIntegrityError
from fastkit_admin.resource.fieldset import Fieldset
from fastkit_admin.resource.query import GridQuery
from fastkit_admin.serialization import (
    CLIENT_FORMATTED_TYPES,
    coerce_identifier,
    grid_value,
    plain_value,
    translate_schema,
)

ModelT = TypeVar("ModelT")


class AdminResource(Generic[ModelT]):
    """Declarative admin resource exposing a CRUD grid, form, filters and actions over a model."""

    name: str = ""
    label: str = ""
    icon: str = "table"
    model: type = object

    list_columns: list = []
    clickable_columns: list[str] | None = None
    search_fields: list[str] = []
    filters: list = []
    actions: list = []
    ordering: list[str] = []
    form_fields: list = []
    fieldsets: list = []
    inlines: list = []
    page_size: int = 25
    max_page_size: int = 100
    select_all: bool = True

    pk_field: str = "id"
    read_only: bool = False
    file_fields: list[str] = []
    files = None
    media_base_url: str = ""

    permissions: dict = {}

    def __init__(self):
        self._field_map = {field.name: field for field in self.form_fields}
        self._filters = [item for item in self.filters if isinstance(item, Filter)]
        self._filter_fieldsets = [
            item for item in self.filters if isinstance(item, Fieldset)
        ]
        self._filter_map = {item.field: item for item in self._filters}
        self._columns = normalize_columns(self.list_columns)
        self._action_map = {action.name: action for action in self.actions}

    # queryset and serialization

    def get_queryset(self):
        return select(self.model)

    def sortable_columns(self) -> set[str]:
        return {column.name for column in self._columns if column.sortable} | set(
            self._field_map.keys()
        )

    def display(self, row) -> str:
        label = getattr(row, "display_label", None)

        if callable(label):
            return str(label())

        return str(getattr(row, self.pk_field))

    def _column_type(self, column) -> str:
        if column.type is not None:
            return column.type

        field = self._field_map.get(column.name)

        return field.field_type if field is not None else "text"

    def serialize_row(self, row, locale: str = "en") -> dict:
        data = {"id": str(getattr(row, self.pk_field))}

        for column in self._columns:
            renderer = getattr(self, f"render_{column.name}", None)

            if renderer is not None:
                data[column.name] = renderer(row, locale)
            elif self._column_type(column) in CLIENT_FORMATTED_TYPES:
                data[column.name] = grid_value(getattr(row, column.name, None))
            elif column.name in self._field_map:
                data[column.name] = self._field_map[column.name].format_value(
                    getattr(row, column.name, None), locale
                )
            else:
                data[column.name] = plain_value(getattr(row, column.name, None))

        return data

    def serialize_detail(self, row, locale: str = "en") -> dict:
        data = {"id": str(getattr(row, self.pk_field)), "_display": self.display(row)}
        html = {}

        for name, admin_field in self._field_map.items():
            if admin_field.write_only or admin_field.virtual:
                continue

            data[name] = admin_field.format_value(getattr(row, name, None), locale)
            renderer = getattr(self, f"render_{name}", None)

            if renderer is not None:
                html[name] = renderer(row, locale)

        data["_html"] = html

        return data

    # querying

    def _apply_search(self, query, search: str | None):
        if not search or not self.search_fields:
            return query

        conditions = [
            getattr(self.model, name).ilike(f"%{search}%")
            for name in self.search_fields
        ]

        return query.where(or_(*conditions))

    def _apply_filters(self, query, filters: dict):
        for field_name, value in filters.items():
            filter_obj = self._filter_map.get(field_name)

            if filter_obj is not None:
                query = filter_obj.apply(query, self.model, value)

        return query

    def _sort_target(self, name: str):
        override = getattr(self, f"sort_{name}", None)

        if override is not None:
            return override()

        return getattr(self.model, name)

    def _apply_ordering(self, query, sort: str | None):
        for column in self._resolve_sort(sort):
            descending = column.startswith("-")
            name = column.lstrip("-")
            attribute = self._sort_target(name)
            query = query.order_by(attribute.desc() if descending else attribute.asc())

        return query

    def _default_ordering(self) -> list[str]:
        return self.ordering or [f"-{self.pk_field}"]

    def _resolve_sort(self, sort: str | None) -> list[str]:
        if sort is None:
            return self._default_ordering()

        name = sort.lstrip("-")

        if name in self.sortable_columns() and (
            hasattr(self.model, name) or hasattr(self, f"sort_{name}")
        ):
            return [sort]

        return self._default_ordering()

    async def list(self, session, query: GridQuery, locale: str = "en") -> dict:
        base = self._apply_filters(
            self._apply_search(self.get_queryset(), query.search), query.filters
        )

        total = int(
            (
                await session.execute(select(func.count()).select_from(base.subquery()))
            ).scalar_one()
        )

        page_size = clamp_page_size(query.page_size, self.page_size, self.max_page_size)
        page = max(query.page, 1)

        ordered = (
            self._apply_ordering(base, query.sort)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = (await session.execute(ordered)).scalars().all()

        await self.resolve(session, rows, locale)

        return {
            "rows": [self.serialize_row(row, locale) for row in rows],
            "pagination": OffsetPage(
                page=page, page_size=page_size, total_items=total
            ).to_meta(),
        }

    async def resolve(self, session, rows, locale: str = "en") -> None:
        """Bulk-load related data onto the fetched rows before serialization (avoids N+1 in render_ methods)."""

    async def get_object(self, session, identifier):
        column = getattr(self.model, self.pk_field)

        if isinstance(column.type, Integer):
            coerced = coerce_identifier(identifier)

            if not isinstance(coerced, int):
                raise NotFoundError(
                    RESOURCE_NOT_FOUND, message=f"{self.label or self.name} not found"
                )
        else:
            coerced = identifier

        row = (
            await session.execute(self.get_queryset().where(column == coerced))
        ).scalar_one_or_none()

        if row is None:
            raise NotFoundError(
                RESOURCE_NOT_FOUND, message=f"{self.label or self.name} not found"
            )

        return row

    # writes

    def _parse_and_validate(self, data: dict, locale: str, partial: bool) -> dict:
        parsed = {}

        for name, admin_field in self._field_map.items():
            if admin_field.readonly or admin_field.virtual:
                continue

            if partial and name not in data:
                continue

            raw = data.get(name)

            if isinstance(admin_field, PasswordField) and (raw is None or raw == ""):
                continue

            value = admin_field.parse_value(raw, locale)
            admin_field.validate(value)
            parsed[name] = value

        return parsed

    def _guard_writable(self) -> None:
        if self.read_only:
            raise AuthorizationError(
                AUTHORIZATION_DENIED, message=f"{self.label or self.name} is read-only"
            )

    def _validate_inlines(self, data: dict, locale: str) -> dict:
        validated = {}
        errors = []

        for inline in self.inlines:
            submitted = data.get(inline.name)

            if isinstance(submitted, list):
                parsed = inline.validate(submitted, locale, errors)

                if parsed is not None:
                    validated[inline.name] = parsed

        if errors:
            raise ValidationError(VALIDATION_FAILED, field_errors=errors)

        return validated

    async def _save_inlines(self, session, row, validated: dict) -> None:
        parent_id = getattr(row, self.pk_field)

        for inline in self.inlines:
            if inline.name in validated:
                try:
                    await inline.persist(session, parent_id, validated[inline.name])
                except InlineIntegrityError as failure:
                    raise self._integrity_error(
                        failure.error, inline, validated[inline.name], [failure.index]
                    ) from failure.error
                except IntegrityError as error:
                    raise self._integrity_error(
                        error, inline, validated[inline.name]
                    ) from error

    async def inline_values(self, session, row, locale: str = "en") -> dict:
        parent_id = getattr(row, self.pk_field)

        return {
            inline.name: await inline.load(session, parent_id, locale)
            for inline in self.inlines
        }

    async def create(self, session, data: dict, locale: str = "en"):
        self._guard_writable()
        parsed = self._parse_and_validate(data, locale, partial=False)
        validated = self._validate_inlines(data, locale)

        try:
            parsed = await self.before_create(session, parsed)
            row = self.model(**parsed)
            session.add(row)
            await session.flush()
            await self.after_create(session, row)
            await session.flush()
            await self._save_inlines(session, row, validated)
            await session.commit()
        except IntegrityError as error:
            await session.rollback()
            raise self._integrity_error(error) from error
        except FastKitError:
            await session.rollback()
            raise

        await session.refresh(row)
        await self._sync_files(row)

        return row

    def _integrity_error(
        self,
        error,
        inline=None,
        inline_rows: list | None = None,
        inline_indexes: list[int] | None = None,
    ):
        violation = classify_integrity_error(error)
        editable_fields = [
            name
            for name, field in self._field_map.items()
            if not field.virtual and not field.readonly
        ]
        fields = (
            integrity_fields(self.model, editable_fields, violation)
            if inline is None
            else []
        )
        label = self.label or self.name

        if violation.kind == "unique":
            errors = (
                inline.integrity_errors(
                    violation, inline_rows or [], "validation.unique", inline_indexes
                )
                if inline is not None
                else [FieldError(field, "validation.unique") for field in fields]
            )

            return ConflictError(
                CONFLICT_UNIQUE,
                message=f"a {label} with these values already exists",
                field_errors=errors,
            )

        if violation.kind == "foreign_key":
            errors = (
                inline.integrity_errors(
                    violation,
                    inline_rows or [],
                    "validation.foreign-key",
                    inline_indexes,
                )
                if inline is not None
                else [FieldError(field, "validation.foreign-key") for field in fields]
            )

            return ValidationError(
                VALIDATION_FAILED,
                message="a referenced record does not exist",
                field_errors=errors,
            )

        if violation.kind == "not_null":
            errors = (
                inline.integrity_errors(
                    violation, inline_rows or [], "validation.required", inline_indexes
                )
                if inline is not None
                else [FieldError(field, "validation.required") for field in fields]
            )

            return ValidationError(
                VALIDATION_FAILED,
                message="a required value is missing",
                field_errors=errors,
            )

        if violation.kind == "check":
            errors = (
                inline.integrity_errors(
                    violation, inline_rows or [], "validation.invalid", inline_indexes
                )
                if inline is not None
                else [FieldError(field, "validation.invalid") for field in fields]
            )

            return ValidationError(
                VALIDATION_FAILED,
                message="a value violates a database constraint",
                field_errors=errors,
            )

        return ConflictError(
            CONFLICT_STATE, message="the operation conflicts with the current state"
        )

    async def update(
        self, session, identifier, data: dict, locale: str = "en", partial: bool = False
    ):
        self._guard_writable()
        row = await self.get_object(session, identifier)
        parsed = self._parse_and_validate(data, locale, partial=partial)
        validated = self._validate_inlines(data, locale)

        try:
            parsed = await self.before_update(session, row, parsed)

            for name, value in parsed.items():
                setattr(row, name, value)

            await self.after_update(session, row)
            await session.flush()
            await self._save_inlines(session, row, validated)
            await session.commit()
        except IntegrityError as error:
            await session.rollback()
            raise self._integrity_error(error) from error
        except FastKitError:
            await session.rollback()
            raise

        await session.refresh(row)
        await self._sync_files(row)

        return row

    async def delete(self, session, identifier) -> None:
        self._guard_writable()
        row = await self.get_object(session, identifier)
        await self.before_delete(session, row)
        owner_id = getattr(row, self.pk_field)
        await session.delete(row)
        await session.commit()
        await self._unlink_files(owner_id)

    async def _sync_files(self, row) -> None:
        if self.files is None:
            return

        owner_id = getattr(row, self.pk_field)

        for name in self.file_fields:
            await self.files.link_slot(
                self.name, owner_id, name, self._object_key(getattr(row, name, None))
            )

    async def _unlink_files(self, owner_id) -> None:
        if self.files is None:
            return

        await self.files.unlink_owner(self.name, owner_id)

    def _object_key(self, value) -> str | None:
        prefix = f"{self.media_base_url}/"

        if not value or not isinstance(value, str) or not value.startswith(prefix):
            return None

        return value[len(prefix) :]

    # custom actions

    def get_action(self, name: str):
        action = self._action_map.get(name)

        if action is None:
            raise NotFoundError(
                RESOURCE_NOT_FOUND, message=f"action '{name}' is not defined"
            )

        return action

    async def run_action(
        self, session, action_name: str, identifiers: list, locale: str = "en"
    ) -> dict:
        self.get_action(action_name)
        handler = getattr(self, f"action_{action_name}", None)

        if handler is None:
            raise NotFoundError(
                RESOURCE_NOT_FOUND, message=f"action '{action_name}' has no handler"
            )

        rows = [
            await self.get_object(session, identifier) for identifier in identifiers
        ]
        result = await handler(session, rows, locale)

        return result if isinstance(result, dict) else {"affected": len(rows)}

    # schemas and permissions

    async def permission_flags(self, check) -> dict:
        flags = {}

        for action in ("list", "detail", "create", "update", "delete"):
            if self.read_only and action in ("create", "update", "delete"):
                flags[f"can_{action}"] = False
                continue

            permission = self.permissions.get(action)
            flags[f"can_{action}"] = (
                True if permission is None else await check(permission)
            )

        return flags

    def _is_clickable(self, column) -> bool:
        if self.clickable_columns is None:
            return True

        return column.name in self.clickable_columns

    def _column_schema(self, column) -> dict:
        schema = column.to_schema()
        schema["field_type"] = self._column_type(column)
        schema["html"] = getattr(self, f"render_{column.name}", None) is not None
        schema["clickable"] = self._is_clickable(column)

        return schema

    def grid_schema(self, flags: dict | None = None, translate=None) -> dict:
        schema = {
            "resource": self.name,
            "label": self.label or self.name,
            "columns": [self._column_schema(column) for column in self._columns],
            "filters": [item.to_schema() for item in self._filters],
            "filter_fieldsets": [
                {
                    "title": fieldset.title,
                    "description": fieldset.description,
                    "fields": fieldset.fields,
                }
                for fieldset in self._filter_fieldsets
            ],
            "actions": [action.to_schema() for action in self.actions],
            "search_fields": self.search_fields,
            "default_sort": self._default_ordering(),
            "page_size": self.page_size,
            "page_size_options": [10, 25, 50, 100],
            "select_all": self.select_all,
            "permissions": self.permissions,
            "flags": flags or {},
        }

        if translate is not None:
            translate_schema(schema, translate)

        return schema

    def form_schema(self, mode: str = "create", translate=None) -> dict:
        available = {
            admin_field.name: admin_field
            for admin_field in self.form_fields
            if not (mode == "create" and admin_field.readonly)
        }

        if self.fieldsets:
            groups = self.fieldsets
        else:
            groups = [
                Fieldset(
                    title=None,
                    fields=[admin_field.name for admin_field in self.form_fields],
                )
            ]

        fieldsets = [
            {
                "title": group.title,
                "description": group.description,
                "fields": [
                    available[name].to_schema()
                    for name in group.fields
                    if name in available
                ],
            }
            for group in groups
        ]
        fieldsets = [fieldset for fieldset in fieldsets if fieldset["fields"]]

        schema = {
            "resource": self.name,
            "mode": mode,
            "fieldsets": fieldsets,
            "inlines": [inline.schema() for inline in self.inlines],
            "actions": [{"name": "save", "label": "Save", "variant": "primary"}],
        }

        if translate is not None:
            translate_schema(schema, translate)

        return schema

    async def relation_options(
        self, session, field_name: str, parent_values: dict, locale: str = "en"
    ) -> list[dict]:
        handler = getattr(self, f"options_{field_name}", None)

        if handler is None:
            raise NotFoundError(
                RESOURCE_NOT_FOUND, message=f"relation '{field_name}' is not defined"
            )

        return await handler(session, parent_values, locale)

    # hooks

    async def before_create(self, session, data: dict) -> dict:
        return data

    async def after_create(self, session, row) -> None:
        pass

    async def before_update(self, session, row, data: dict) -> dict:
        return data

    async def after_update(self, session, row) -> None:
        pass

    async def before_delete(self, session, row) -> None:
        pass
