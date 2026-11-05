from enum import StrEnum


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
