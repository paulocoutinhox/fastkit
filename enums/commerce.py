from enums.purchase_status import PurchaseStatus

# What a gateway said for good, so a later notice about the same purchase is a correction and never the first word.
SETTLED_PURCHASE_STATUSES = frozenset({PurchaseStatus.PAID, PurchaseStatus.REFUNDED, PurchaseStatus.CHARGED_BACK})
