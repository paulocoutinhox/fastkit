from decimal import Decimal

from enums.interval_unit import IntervalUnit
from schemas.base_schema import BaseSchema


class CatalogPlanSchema(BaseSchema):
    """What a client is offered, where the image is an address and never the key the admin edits."""

    id: int
    uuid: str
    code: str
    name: str
    description: str | None
    image_url: str | None
    currency: str
    price: Decimal
    billing_interval_unit: IntervalUnit | None
    billing_interval_value: int | None
    featured: bool
