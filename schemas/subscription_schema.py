from datetime import datetime

from enums.benefit_status import BenefitStatus
from enums.environment import Environment
from enums.subscription_status import SubscriptionStatus
from schemas.plan_reference import PlanReference
from schemas.tenant_reference import TenantReference
from schemas.timestamp_schema import TimestampSchema
from schemas.user_reference import UserReference


class SubscriptionSchema(TimestampSchema):
    id: int
    tenant_id: int | None
    tenant: TenantReference | None
    user_id: int
    user: UserReference | None
    plan_id: int
    plan: PlanReference | None
    integration_id: int | None
    external_product_id: int | None
    external_id: str | None
    status: SubscriptionStatus
    benefit_status: BenefitStatus
    environment: Environment | None
    started_at: datetime | None
    current_period_started_at: datetime | None
    current_period_ends_at: datetime | None
    access_until: datetime | None
    trial_ends_at: datetime | None
    grace_until: datetime | None
    cancel_at_period_end: bool
    canceled_at: datetime | None
    expired_at: datetime | None
    meta: dict
