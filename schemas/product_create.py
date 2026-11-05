from decimal import Decimal

from pydantic import Field

from schemas.base_schema import BaseSchema
from schemas.common import FREE_TEXT_MAX, JsonMap, OptionalReference, Position, Price, Quantity, Text


class ProductCreate(BaseSchema):
    tenant_id: OptionalReference
    name: Text(255)
    slug: str | None = Field(None, max_length=255)
    description: str | None = Field(None, max_length=FREE_TEXT_MAX)
    image: str | None = Field(None, max_length=512)
    file: str | None = Field(None, max_length=512)
    currency: str = Field("USD", min_length=3, max_length=3)
    price: Price = Decimal("0")
    credits: Quantity = 0
    credits_currency_id: OptionalReference
    featured: bool = False
    position: Position
    active: bool = True
    meta: JsonMap = Field(default_factory=dict)
