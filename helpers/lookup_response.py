"""The lookup response shared by application modules."""

from helpers.lookup_item import LookupItem
from schemas.base_schema import BaseSchema


class LookupResponse(BaseSchema):
    items: list[LookupItem]
