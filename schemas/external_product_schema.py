from decimal import Decimal

from schemas.integration_reference import IntegrationReference
from schemas.plan_reference import PlanReference
from schemas.timestamp_schema import TimestampSchema


class ExternalProductSchema(TimestampSchema):
    id: int
    integration_id: int
    integration: IntegrationReference | None
    plan_id: int
    plan: PlanReference | None
    external_id: str
    display_name: str | None
    reference_currency: str | None
    reference_price: Decimal | None
    notes: str | None
    active: bool
    meta: dict
