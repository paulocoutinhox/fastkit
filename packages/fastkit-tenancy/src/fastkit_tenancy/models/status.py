from enum import Enum


class TenantStatus(str, Enum):
    active = "active"
    suspended = "suspended"
    disabled = "disabled"
