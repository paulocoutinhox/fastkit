from enum import StrEnum


class SubscriptionStatus(StrEnum):
    PENDING = "pending"
    TRIALING = "trialing"
    ACTIVE = "active"
    GRACE_PERIOD = "grace-period"
    SUSPENDED = "suspended"
    EXPIRED = "expired"
    REVOKED = "revoked"
