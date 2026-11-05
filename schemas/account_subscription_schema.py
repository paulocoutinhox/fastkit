from datetime import datetime

from enums.benefit_status import BenefitStatus
from enums.subscription_status import SubscriptionStatus
from schemas.plan_reference import PlanReference
from schemas.timestamp_schema import TimestampSchema


class AccountSubscriptionSchema(TimestampSchema):
    """What an account reads about what it pays for, without the ids the admin needs."""

    id: int
    plan: PlanReference
    status: SubscriptionStatus
    benefit_status: BenefitStatus
    started_at: datetime | None
    current_period_started_at: datetime | None
    current_period_ends_at: datetime | None
    access_until: datetime | None
    trial_ends_at: datetime | None
    grace_until: datetime | None
    cancel_at_period_end: bool
    canceled_at: datetime | None
    expired_at: datetime | None
