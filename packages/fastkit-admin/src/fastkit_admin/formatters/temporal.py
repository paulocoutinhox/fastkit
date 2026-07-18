from datetime import date, datetime, time

from fastkit_admin.formatters.locale_format import locale_format


def format_date(value: date, locale: str = "en") -> str:
    return value.strftime(locale_format(locale).date_format)


def format_datetime(value: datetime, locale: str = "en") -> str:
    return value.strftime(locale_format(locale).datetime_format)


def parse_date(raw: str, locale: str = "en") -> date:
    text = raw.strip()

    for pattern in ("%Y-%m-%d", locale_format(locale).date_format):
        try:
            return datetime.strptime(text, pattern).date()
        except ValueError:
            continue

    raise ValueError(f"invalid date value '{raw}'")


def parse_datetime(raw: str, locale: str = "en") -> datetime:
    text = raw.strip().replace("T", " ")

    for pattern in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        locale_format(locale).datetime_format,
    ):
        try:
            return datetime.strptime(text, pattern)
        except ValueError:
            continue

    raise ValueError(f"invalid datetime value '{raw}'")


def format_time(value: time, locale: str = "en") -> str:
    return value.strftime(locale_format(locale).time_format)


def parse_time(raw: str, locale: str = "en") -> time:
    text = raw.strip()

    for pattern in ("%H:%M:%S", "%H:%M"):
        try:
            return datetime.strptime(text, pattern).time()
        except ValueError:
            continue

    raise ValueError(f"invalid time value '{raw}'")
