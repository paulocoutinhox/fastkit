from enum import StrEnum


class Provider(StrEnum):
    REVENUECAT = "revenuecat"
    STRIPE = "stripe"


class Environment(StrEnum):
    SANDBOX = "sandbox"
    PRODUCTION = "production"


class WebhookEventStatus(StrEnum):
    RECEIVED = "received"
    PROCESSING = "processing"
    COMPLETED = "completed"
    IGNORED = "ignored"
    FAILED = "failed"


class NormalizedAction(StrEnum):
    ACTIVATE = "activate"
    RENEW = "renew"
    CANCEL_AT_PERIOD_END = "cancel-at-period-end"
    SUSPEND = "suspend"
    RESUME = "resume"
    EXPIRE = "expire"
    REFUND = "refund"
    CHANGE_PLAN = "change-plan"
    ENTER_GRACE = "enter-grace"
    EXTEND = "extend"
