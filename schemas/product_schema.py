from decimal import Decimal

from schemas.currency_reference import CurrencyReference
from schemas.tenant_reference import TenantReference
from schemas.timestamp_schema import TimestampSchema


class ProductSchema(TimestampSchema):
    id: int
    uuid: str
    tenant_id: int | None
    tenant: TenantReference | None
    name: str
    slug: str
    description: str | None
    image: str | None
    file: str | None
    currency: str
    price: Decimal
    credits: int
    credits_currency_id: int | None
    credits_currency: CurrencyReference | None
    featured: bool
    position: int
    active: bool
    meta: dict
