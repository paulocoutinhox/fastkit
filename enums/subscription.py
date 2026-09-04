from enum import StrEnum


class IntervalUnit(StrEnum):
    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    YEAR = "year"


class BenefitPolicy(StrEnum):
    NONE = "none"
    ACCESS_ONLY = "access_only"
    ALL = "all"


class ResumeDeliveryPolicy(StrEnum):
    """What a plan owes somebody who comes back, where coming back is most often a bill paid late."""

    SAME_CYCLE = "same_cycle"
    NEW_CYCLE = "new_cycle"


class BenefitType(StrEnum):
    ACCESS = "access"
    CREDIT = "credit"
    PRODUCT = "product"


class BenefitCadence(StrEnum):
    ON_ACTIVATION = "on_activation"
    RECURRING = "recurring"
    ONCE_PER_USER = "once_per_user"


class MissedCyclePolicy(StrEnum):
    SKIP = "skip"
    LATEST_ONLY = "latest_only"
    CATCH_UP = "catch_up"


class SubscriptionStatus(StrEnum):
    PENDING = "pending"
    TRIALING = "trialing"
    ACTIVE = "active"
    GRACE_PERIOD = "grace_period"
    SUSPENDED = "suspended"
    EXPIRED = "expired"
    REVOKED = "revoked"


class BenefitStatus(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    ENDED = "ended"


class UserEntitlementStatus(StrEnum):
    ACTIVE = "active"
    EXPIRED = "expired"


class BenefitGrantStatus(StrEnum):
    PROCESSING = "processing"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    FAILED = "failed"


ELIGIBLE_SUBSCRIPTION_STATUSES = frozenset({SubscriptionStatus.TRIALING, SubscriptionStatus.ACTIVE, SubscriptionStatus.GRACE_PERIOD})

SCHEDULE_ADVANCE_STATUSES = frozenset({BenefitGrantStatus.COMPLETED, BenefitGrantStatus.SKIPPED})

# What a gateway naming its own state calls a subscription that is finished, so nothing here has to read it off the dates.
CLOSED_SUBSCRIPTION_STATUSES = frozenset({SubscriptionStatus.EXPIRED, SubscriptionStatus.REVOKED})
