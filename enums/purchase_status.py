from enum import StrEnum


class PurchaseStatus(StrEnum):
    PENDING = "pending"
    PAID = "paid"
    CANCELED = "canceled"
    FAILED = "failed"
    REFUNDED = "refunded"
    CHARGED_BACK = "charged-back"
