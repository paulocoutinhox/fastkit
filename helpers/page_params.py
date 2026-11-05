"""The page params shared by application modules."""

from schemas.base_schema import BaseSchema


class PageParams(BaseSchema):
    limit: int
    offset: int
    search: str | None = None
    ordering: str | None = None
