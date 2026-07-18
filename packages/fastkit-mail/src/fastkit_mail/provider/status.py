from enum import Enum


class ProviderStatus(str, Enum):
    healthy = "healthy"
    unavailable = "unavailable"
