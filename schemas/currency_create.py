from pydantic import Field

from schemas.base_schema import BaseSchema
from schemas.common import JsonMap, OptionalReference, Position, Text


class CurrencyCreate(BaseSchema):
    tenant_id: OptionalReference
    code: str | None = Field(None, max_length=32)
    name: Text(128)
    symbol: str | None = Field(None, max_length=8)
    position: Position
    active: bool = True
    meta: JsonMap = Field(default_factory=dict)
