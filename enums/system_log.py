from enum import StrEnum


class LogLevel(StrEnum):
    DEBUG = "debug"
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"


class LogCategory(StrEnum):
    """Where an entry came from, closed so the admin can filter by it the same way it filters by level."""

    CRON = "cron"
    ADMIN = "admin"
    ACCOUNT = "account"
    PURCHASE = "purchase"
    CONTENT = "content"
