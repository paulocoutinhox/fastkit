from decimal import Decimal

from schemas.base_schema import BaseSchema


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
    credits_currency: str | None
    featured: bool
