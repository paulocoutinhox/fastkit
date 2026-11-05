from pydantic import Field

from schemas.base_schema import BaseSchema
from schemas.common import JsonMap, Reference


class PlanEntitlementCreate(BaseSchema):
    plan_id: Reference
    entitlement_id: Reference
    meta: JsonMap = Field(default_factory=dict)
