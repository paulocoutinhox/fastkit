from enum import Enum


class StorageStatus(str, Enum):
    healthy = "healthy"
    unavailable = "unavailable"
