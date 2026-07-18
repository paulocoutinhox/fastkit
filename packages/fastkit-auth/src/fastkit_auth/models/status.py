from enum import Enum


class SessionStatus(str, Enum):
    active = "active"
    expired = "expired"
    revoked = "revoked"
