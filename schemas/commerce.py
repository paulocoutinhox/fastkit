from datetime import datetime
from decimal import Decimal

from pydantic import Field

from enums.commerce import PurchaseStatus
from schemas.account import CurrencyReference
from schemas.common import FREE_TEXT_MAX, BaseSchema, OptionalReference, Position, Quantity, Text, TimestampSchema, as_optional
from schemas.tenant import TenantReference
from schemas.user import UserReference


class ProductReference(BaseSchema):
    id: int
    uuid: str
    name: str
    slug: str


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


class ProductCreate(BaseSchema):
    tenant_id: OptionalReference
    name: Text(255)
    slug: str | None = Field(None, max_length=255)
    description: str | None = Field(None, max_length=FREE_TEXT_MAX)
    image: str | None = Field(None, max_length=512)
    file: str | None = Field(None, max_length=512)
    currency: str = Field("USD", min_length=3, max_length=3)
    price: Decimal = Field(Decimal("0"), ge=0)
    credits: Quantity = 0
    credits_currency_id: OptionalReference
    featured: bool = False
    position: Position
    active: bool = True
    meta: dict = Field(default_factory=dict)


ProductUpdate = as_optional("ProductUpdate", ProductCreate)


class SiteProductSchema(BaseSchema):
    """A product card of the site, which is what the page draws and therefore what is kept for the next reader."""

    id: int
    uuid: str
    name: str
    slug: str
    description: str | None
    image_url: str | None
    currency: str
    price: Decimal
    credits: int
    credits_currency: str | None


class CatalogEntrySchema(BaseSchema):
    """What every reader of a tenant is answered the same, with the image resolved into an address instead of a storage key."""

    id: int
    uuid: str
    name: str
    slug: str
    description: str | None
    image_url: str | None
    currency: str
    price: Decimal
    credits: int
    featured: bool


class CatalogProductSchema(CatalogEntrySchema):
    """What a visitor reads, which is the catalogue plus the one thing that belongs to their account alone."""

    owned: bool


class PurchaseSchema(TimestampSchema):
    id: int
    tenant_id: int | None
    tenant: TenantReference | None
    user_id: int
    user: UserReference | None
    product_id: int
    product: ProductReference | None
    integration_id: int | None
    reference: str
    external_id: str | None
    currency: str
    price: Decimal
    status: PurchaseStatus
    paid_at: datetime | None
    meta: dict


class AccountPurchaseSchema(TimestampSchema):
    """The statement of whoever is asking, so naming the account on every line would say nothing."""

    id: int
    product: ProductReference
    reference: str
    currency: str
    price: Decimal
    status: PurchaseStatus
    paid_at: datetime | None


class UserProductSchema(TimestampSchema):
    id: int
    user_id: int
    user: UserReference | None
    product_id: int
    product: ProductReference | None
    purchase_id: int | None
    subscription_id: int | None
    benefit_grant_id: int | None
    granted_at: datetime
    meta: dict


class AccountProductSchema(BaseSchema):
    """What the account owns, where the address of the file is only ever built for somebody who owns it."""

    id: int
    uuid: str
    name: str
    slug: str
    description: str | None
    image_url: str | None
    file_url: str | None
    granted_at: datetime
