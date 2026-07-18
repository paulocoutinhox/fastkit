from enum import Enum


class WebhookStatus(str, Enum):
    received = "received"
    processing = "processing"
    processed = "processed"
    retrying = "retrying"
    failed = "failed"
    rejected = "rejected"
