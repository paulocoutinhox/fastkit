from enum import Enum


class DeliveryStatus(str, Enum):
    pending = "pending"
    queued = "queued"
    sending = "sending"
    sent = "sent"
    retrying = "retrying"
    failed = "failed"
    cancelled = "cancelled"
