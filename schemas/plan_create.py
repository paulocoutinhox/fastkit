from decimal import Decimal

from pydantic import Field

from enums.benefit_policy import BenefitPolicy
from enums.interval_unit import IntervalUnit
from enums.resume_delivery_policy import ResumeDeliveryPolicy
from schemas.base_schema import BaseSchema
from schemas.common import FREE_TEXT_MAX, IntervalValue, JsonMap, OptionalReference, Position, Price, Text


class PlanCreate(BaseSchema):
    tenant_id: OptionalReference
    language_id: OptionalReference
    code: str | None = Field(None, max_length=64)
    name: Text(255)
    description: str | None = Field(None, max_length=FREE_TEXT_MAX)
    image: str | None = Field(None, max_length=512)
    currency: str = Field("USD", min_length=3, max_length=3)
    price: Price = Decimal("0")
    billing_interval_unit: IntervalUnit | None = None
    billing_interval_value: IntervalValue
    resume_delivery_policy: ResumeDeliveryPolicy = ResumeDeliveryPolicy.SAME_CYCLE
    trial_benefit_policy: BenefitPolicy = BenefitPolicy.ACCESS_ONLY
    grace_benefit_policy: BenefitPolicy = BenefitPolicy.ACCESS_ONLY
    featured: bool = False
    position: Position
    active: bool = True
    meta: JsonMap = Field(default_factory=dict)
