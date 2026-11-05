"""The lookup item shared by application modules."""

from schemas.base_schema import BaseSchema


class LookupItem(BaseSchema):
    id: int
    label: str
