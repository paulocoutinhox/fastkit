from enum import Enum


class UploadStatus(str, Enum):
    pending = "pending"
    confirmed = "confirmed"
    expired = "expired"
