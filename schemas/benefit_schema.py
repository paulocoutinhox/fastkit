from enums.benefit_cadence import BenefitCadence
from enums.benefit_type import BenefitType
from enums.interval_unit import IntervalUnit
from enums.missed_cycle_policy import MissedCyclePolicy
from schemas.currency_reference import CurrencyReference
from schemas.entitlement_reference import EntitlementReference
from schemas.product_reference import ProductReference
from schemas.timestamp_schema import TimestampSchema


class BenefitSchema(TimestampSchema):
    id: int
    entitlement_id: int
    entitlement: EntitlementReference | None
    product_id: int | None
    product: ProductReference | None
    currency_id: int | None
    currency: CurrencyReference | None
    type: BenefitType
    target: str
    quantity: int
    cadence: BenefitCadence
    interval_unit: IntervalUnit | None
    interval_value: int | None
    grant_on_activation: bool
    missed_cycle_policy: MissedCyclePolicy
    active: bool
    meta: dict
