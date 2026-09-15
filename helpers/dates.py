"""Every instant this project reads or writes, which is UTC and never the clock of a machine."""

from calendar import monthrange
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from enums.subscription import IntervalUnit

# How far one of each unit walks, in days and in months, because a month is not a count of days.
STEPS = {IntervalUnit.DAY: (1, 0), IntervalUnit.WEEK: (7, 0), IntervalUnit.MONTH: (0, 1), IntervalUnit.YEAR: (0, 12)}


def now() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(value: datetime | None) -> datetime | None:
    """Every timestamp is stored in UTC, so a naive value is read as UTC and an aware one is converted."""
    if value is None:
        return None

    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)

    return value.astimezone(timezone.utc)


def read_in(value: datetime, zone: str, shape: str) -> str:
    """An instant as the clock of whoever is reading it shows, because a purchase made at nine in the evening is not one made the next day."""
    return as_utc(value).astimezone(ZoneInfo(zone)).strftime(shape)


def naive_utc(value: datetime | None) -> datetime | None:
    """MySQL columns hold no offset, so what reaches the driver is always the naive UTC instant."""
    converted = as_utc(value)

    if converted is None:
        return None

    return converted.replace(tzinfo=None)


def add_months(moment: datetime, months: int) -> datetime:
    """A day missing from the target month lands on its last day, so a cycle anchored on the 31st survives february."""
    total = moment.month - 1 + months
    year = moment.year + total // 12
    month = total % 12 + 1
    day = min(moment.day, monthrange(year, month)[1])

    return moment.replace(year=year, month=month, day=day)


def add_interval(moment: datetime, unit: IntervalUnit, value: int) -> datetime:
    """Every unit is named, so one nobody declared raises here instead of quietly meaning a year."""
    days, months = STEPS[unit]

    return add_months(moment + timedelta(days=days * value), months * value)
