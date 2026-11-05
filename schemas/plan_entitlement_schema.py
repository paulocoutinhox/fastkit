from schemas.entitlement_reference import EntitlementReference
from schemas.plan_reference import PlanReference
from schemas.timestamp_schema import TimestampSchema


class PlanEntitlementSchema(TimestampSchema):
    id: int
    plan_id: int
    plan: PlanReference | None
    entitlement_id: int
    entitlement: EntitlementReference | None
    meta: dict
