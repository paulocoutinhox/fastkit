from enum import StrEnum


class AppEventName(StrEnum):
    """The names this side knows what to do with, where everything else a client reports is stored and closed as ignored."""

    CONTENT_VIEWED = "content_viewed"
    GALLERY_VIEWED = "gallery_viewed"
    CHECKOUT_STARTED = "checkout_started"
    PRODUCT_PURCHASED = "product_purchased"


class AppEventStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    PROCESSED = "processed"
    IGNORED = "ignored"
    FAILED = "failed"
