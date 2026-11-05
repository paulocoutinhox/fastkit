"""The page shared by application modules."""

from typing import Generic, TypeVar

from schemas.base_schema import BaseSchema

Item = TypeVar("Item")


class Page(BaseSchema, Generic[Item]):
    count: int
    limit: int
    offset: int
    items: list[Item]
