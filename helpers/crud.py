"""The routes every resource of the panel answers, built out of what its service declares."""

from enum import Enum
from typing import Annotated, Type

from fastapi import APIRouter, Depends, Path, Query, Request, Response, status
from pydantic import BaseModel, Field
from pydantic.alias_generators import to_camel

from helpers import audit
from helpers.auth import CurrentUser, requires
from helpers.db import DatabaseSession
from helpers.errors import PermissionError, ValidationError
from helpers.pagination import CurrentPage, Page
from models.base import BIG_INTEGER_MAX
from models.user import User
from schemas.common import BaseSchema
from services.crud import CrudService

PAGE_PARAMS = frozenset({"limit", "offset", "search", "ordering"})

LOOKUP_PARAMS = frozenset({"limit", "search"})

TRUE_VALUES = {"true", "1", "yes"}

FALSE_VALUES = {"false", "0", "no"}

# What each resource of the API is served by, filled by whoever registers the routers so a router built and never registered is in nothing.
RESOURCES: dict[str, CrudService] = {}

# An identifier the driver can carry, because one it cannot overflows inside the query and answers a 500.
RecordId = Annotated[int, Path(ge=1, le=BIG_INTEGER_MAX)]


class LookupItem(BaseSchema):
    id: int
    label: str


class LookupResponse(BaseSchema):
    items: list[LookupItem]


class ReorderRequest(BaseSchema):
    """The ids in the order they should stand, which is the whole instruction."""

    ids: list[int] = Field(min_length=1, max_length=200)


def coerce(column, raw: str):
    """Filters arrive as text on the query string and are read through the column they target."""
    if raw == "":
        return None

    python_type = column.type.python_type

    if python_type is bool:
        lowered = raw.lower()

        if lowered in TRUE_VALUES:
            return True

        if lowered in FALSE_VALUES:
            return False

        raise ValueError(raw)

    if python_type is int:
        if not raw.lstrip("-").isdigit():
            raise ValueError(raw)

        number = int(raw)

        # A number no column holds overflows inside the driver, and the filter is what has to refuse it.
        if not -BIG_INTEGER_MAX <= number <= BIG_INTEGER_MAX:
            raise ValueError(raw)

        return number

    # A value no member of the enum carries matches no row, and answering an empty list reads as a filter that found nothing.
    if isinstance(python_type, type) and issubclass(python_type, Enum):
        return python_type(raw)

    return raw


def parse_filters(service: CrudService, request: Request, reserved: frozenset[str]) -> dict:
    """A filter arrives under the same camelCase name every other field of the API uses."""
    known = {to_camel(name): name for name in service.filter_fields}
    unknown = set(request.query_params) - set(known) - reserved

    # A filter nobody applies would answer the whole list, and whoever misspelled one would read it as filtered.
    if unknown:
        raise ValidationError("error.unknown-query-parameter", parameter=sorted(unknown)[0])

    filters = {}

    for sent, name in known.items():
        if sent not in request.query_params:
            continue

        # A value the column cannot read is refused for the same reason an unknown name is: dropping it answers the whole list as if it were filtered.
        try:
            value = coerce(service.filter_column(name), request.query_params[sent])
        except ValueError as error:
            raise ValidationError("error.invalid-query-parameter", parameter=sent) from error

        if value is not None:
            filters[name] = value

    return filters


def operator_of(service: CrudService):
    """Who is asking, so a listing answers what belongs to them: a catalogue of the system is reached by an operator that belongs to no brand either."""

    async def asking(user: CurrentUser) -> User:
        if service.system_wide and user.tenant_id is not None:
            raise PermissionError()

        return user

    return asking


def build_readonly_router(service: CrudService, read_schema: Type[BaseModel], prefix: str, tag: str) -> APIRouter:
    """The read side every resource answers, where delivery tables stop because the engine writes them."""
    # A catalogue is an option of somebody else's form, so the router lets in whoever may resolve it and every other route narrows to whoever manages it.
    router = APIRouter(prefix=prefix, tags=[tag], dependencies=[Depends(requires(*(service.lookup_roles or service.roles)))])

    # The resource says who reaches it, so a role is changed in one line and never route by route.
    managed = Depends(requires(*service.roles))
    operating = Depends(operator_of(service))
    filter_hint = ", ".join(service.filter_fields) or "none"

    @router.get("", response_model=Page[read_schema], summary=f"List {tag}", description=f"Filterable fields: {filter_hint}.", dependencies=[managed])
    async def list_records(db: DatabaseSession, page: CurrentPage, request: Request, operator: User = operating):
        total, items = await service.paginate(db, page, parse_filters(service, request, PAGE_PARAMS), operator)

        return Page[read_schema](count=total, limit=page.limit, offset=page.offset, items=[read_schema.model_validate(item) for item in items])

    @router.get("/lookup", response_model=LookupResponse, summary=f"Lookup {tag}")
    async def lookup_records(db: DatabaseSession, request: Request, operator: User = operating, search: str | None = Query(None, max_length=128), limit: int = Query(20, ge=1, le=50)):
        items = await service.lookup(db, search, limit, parse_filters(service, request, LOOKUP_PARAMS), operator)

        return LookupResponse(items=[LookupItem(**item) for item in items])

    # The literal segment is declared before the record id route, or the id swallows it.
    @router.get("/lookup/{record_id}", response_model=LookupItem, summary=f"Name one option of {tag}")
    async def lookup_record(db: DatabaseSession, record_id: RecordId, operator: User = operating):
        """A form holding a value the first page of options does not carry still names it, and by the label the API builds."""
        instance = await service.get(db, record_id, operator)

        return LookupItem(id=instance.id, label=service.build_label(instance))

    @router.get("/{record_id}", response_model=read_schema, summary=f"Read one {tag}", dependencies=[managed])
    async def read_record(db: DatabaseSession, record_id: RecordId, operator: User = operating):
        return read_schema.model_validate(await service.get(db, record_id, operator))

    # The router carries what serves it, so the pairing is read off the application instead of written down twice.
    router.served = (prefix.strip("/"), service)

    return router


def build_router(service: CrudService, read_schema: Type[BaseModel], create_schema: Type[BaseModel], update_schema: Type[BaseModel], prefix: str, tag: str) -> APIRouter:
    """The read side plus the three writes, bound to one service."""
    router = build_readonly_router(service, read_schema, prefix, tag)
    managed = Depends(requires(*service.roles))
    operating = Depends(operator_of(service))

    @router.post("", response_model=read_schema, status_code=status.HTTP_201_CREATED, summary=f"Create {tag}", dependencies=[managed])
    async def create_record(db: DatabaseSession, author: CurrentUser, payload: create_schema, operator: User = operating):
        instance = await service.create(db, payload.model_dump(exclude_unset=True), operator)
        await audit.written(db, author, "created", tag, instance.id)

        return read_schema.model_validate(instance)

    # The literal segment is declared first, or the record id route swallows it.
    if service.position_field:

        @router.put("/order", response_model=list[read_schema], summary=f"Reorder {tag}", dependencies=[managed])
        async def reorder_records(db: DatabaseSession, author: CurrentUser, payload: ReorderRequest, operator: User = operating):
            records = await service.reorder(db, payload.ids, operator)
            await audit.written(db, author, "reordered", tag, *payload.ids)

            return [read_schema.model_validate(record) for record in records]

    @router.put("/{record_id}", response_model=read_schema, summary=f"Update {tag}", dependencies=[managed])
    async def update_record(db: DatabaseSession, author: CurrentUser, record_id: RecordId, payload: update_schema, operator: User = operating):
        instance = await service.update(db, record_id, payload.model_dump(exclude_unset=True), operator)
        await audit.written(db, author, "edited", tag, record_id)

        return read_schema.model_validate(instance)

    @router.delete("/{record_id}", status_code=status.HTTP_204_NO_CONTENT, summary=f"Delete {tag}", dependencies=[managed])
    async def delete_record(db: DatabaseSession, author: CurrentUser, record_id: RecordId, operator: User = operating):
        # Nobody deletes the row they are signed in as, which would leave the trail of the deletion pointing at somebody who is gone.
        if service.model is type(author) and record_id == author.id:
            raise ValidationError("error.cannot-delete-yourself")

        await service.delete(db, record_id, operator)
        await audit.written(db, author, "deleted", tag, record_id)

        return Response(status_code=status.HTTP_204_NO_CONTENT)

    return router
