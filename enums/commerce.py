from enum import StrEnum


class PurchaseStatus(StrEnum):
    PENDING = "pending"
    ANALYSIS = "analysis"
    PAID = "paid"
    CANCELED = "canceled"
    FAILED = "failed"
    REFUNDED = "refunded"
    CHARGED_BACK = "charged_back"


# What a gateway said for good, so a later notice about the same purchase is a correction and never the first word.
SETTLED_PURCHASE_STATUSES = frozenset({PurchaseStatus.PAID, PurchaseStatus.REFUNDED, PurchaseStatus.CHARGED_BACK})
