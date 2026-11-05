from decimal import Decimal

from schemas.base_schema import BaseSchema


class PlanReference(BaseSchema):
    id: int
    uuid: str
    code: str
    name: str
    currency: str
    price: Decimal
