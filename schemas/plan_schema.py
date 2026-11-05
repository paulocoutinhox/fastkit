from decimal import Decimal

from enums.benefit_policy import BenefitPolicy
from enums.interval_unit import IntervalUnit
from enums.resume_delivery_policy import ResumeDeliveryPolicy
from schemas.language_reference import LanguageReference
from schemas.tenant_reference import TenantReference
from schemas.timestamp_schema import TimestampSchema


class PlanSchema(TimestampSchema):
    id: int
    uuid: str
    tenant_id: int | None
    tenant: TenantReference | None
    language_id: int | None
    language: LanguageReference | None
    code: str
    name: str
    description: str | None
    image: str | None
    currency: str
    price: Decimal
    billing_interval_unit: IntervalUnit | None
    billing_interval_value: int | None
    resume_delivery_policy: ResumeDeliveryPolicy
    trial_benefit_policy: BenefitPolicy
    grace_benefit_policy: BenefitPolicy
    featured: bool
    position: int
    active: bool
    meta: dict
