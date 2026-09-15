from enum import StrEnum


class AppEventName(StrEnum):
    """The names this side knows what to do with, where everything else a client reports is stored and closed as ignored."""

    CONTENT_VIEWED = "content-viewed"
    GALLERY_VIEWED = "gallery-viewed"
    CHECKOUT_STARTED = "checkout-started"
    PRODUCT_PURCHASED = "product-purchased"


class AppEventStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    PROCESSED = "processed"
    IGNORED = "ignored"
    FAILED = "failed"
