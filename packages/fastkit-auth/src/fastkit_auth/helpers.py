from datetime import datetime, timezone


def ensure_aware(value: datetime) -> datetime:
    """Coerce a datetime to UTC-aware so SQLite's naive values compare with the clock."""

    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)

    return value
