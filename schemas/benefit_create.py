from pydantic import Field

from enums.benefit_cadence import BenefitCadence
from enums.benefit_type import BenefitType
from enums.interval_unit import IntervalUnit
from enums.missed_cycle_policy import MissedCyclePolicy
from schemas.base_schema import BaseSchema
from schemas.common import IntervalValue, JsonMap, OptionalReference, Quantity, Reference, Text


class BenefitCreate(BaseSchema):
    entitlement_id: Reference
    product_id: OptionalReference
    currency_id: OptionalReference
    type: BenefitType
    target: Text(191)
    quantity: Quantity
    cadence: BenefitCadence
    interval_unit: IntervalUnit | None = None
    interval_value: IntervalValue
    grant_on_activation: bool = True
    missed_cycle_policy: MissedCyclePolicy = MissedCyclePolicy.SKIP
    active: bool = True
    meta: JsonMap = Field(default_factory=dict)
