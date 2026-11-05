from datetime import datetime

from enums.benefit_cadence import BenefitCadence
from enums.benefit_status import BenefitStatus
from enums.benefit_type import BenefitType
from enums.interval_unit import IntervalUnit
from enums.missed_cycle_policy import MissedCyclePolicy
from schemas.currency_reference import CurrencyReference
from schemas.product_reference import ProductReference
from schemas.subscription_reference import SubscriptionReference
from schemas.timestamp_schema import TimestampSchema


class SubscriptionBenefitSchema(TimestampSchema):
    id: int
    subscription_id: int
    subscription: SubscriptionReference | None
    benefit_id: int
    user_entitlement_id: int
    product_id: int | None
    product: ProductReference | None
    currency_id: int | None
    currency: CurrencyReference | None
    status: BenefitStatus
    benefit_type: BenefitType
    target: str
    quantity: int
    cadence: BenefitCadence
    interval_unit: IntervalUnit | None
    interval_value: int | None
    grant_on_activation: bool
    missed_cycle_policy: MissedCyclePolicy
    anchor_at: datetime
    last_grant_at: datetime | None
    next_grant_at: datetime | None
    meta: dict
