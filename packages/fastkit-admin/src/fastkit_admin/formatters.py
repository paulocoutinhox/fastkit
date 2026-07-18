from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation


@dataclass(frozen=True)
class LocaleFormat:
    thousands: str
    decimal: str
    date_format: str
    datetime_format: str
    time_format: str = "%H:%M"


LOCALE_FORMATS = {
    "en": LocaleFormat(
        thousands=",",
        decimal=".",
        date_format="%m/%d/%Y",
        datetime_format="%m/%d/%Y %H:%M",
    ),
    "pt": LocaleFormat(
        thousands=".",
        decimal=",",
        date_format="%d/%m/%Y",
        datetime_format="%d/%m/%Y %H:%M",
    ),
    "es": LocaleFormat(
        thousands=".",
        decimal=",",
        date_format="%d/%m/%Y",
        datetime_format="%d/%m/%Y %H:%M",
    ),
}


def locale_format(locale: str) -> LocaleFormat:
    return LOCALE_FORMATS.get(locale.split("_")[0].lower(), LOCALE_FORMATS["en"])


class DecimalParseError(ValueError):
    pass


def format_decimal(
    value: Decimal | int | float, locale: str = "en", decimal_places: int = 2
) -> str:
    """Render a number with locale-aware thousands and decimal separators."""

    fmt = locale_format(locale)
    quantized = Decimal(str(value)).quantize(Decimal(1).scaleb(-decimal_places))
    sign = "-" if quantized < 0 else ""
    integer, _, fraction = f"{abs(quantized):.{decimal_places}f}".partition(".")

    grouped = ""
    for index, digit in enumerate(reversed(integer)):
        if index and index % 3 == 0:
            grouped = fmt.thousands + grouped
        grouped = digit + grouped

    if decimal_places == 0:
        return f"{sign}{grouped}"

    return f"{sign}{grouped}{fmt.decimal}{fraction}"


def parse_decimal(raw: str | Decimal | int | float, locale: str = "en") -> Decimal:
    """Parse a user-entered number, accepting the locale separators or a canonical form."""

    if isinstance(raw, Decimal):
        return raw

    if isinstance(raw, (int, float)):
        return Decimal(str(raw))

    fmt = locale_format(locale)
    text = raw.strip()

    if not text:
        raise DecimalParseError("empty decimal value")

    text = text.replace(fmt.thousands, "")

    if fmt.decimal != ".":
        text = text.replace(fmt.decimal, ".")

    try:
        return Decimal(text)
    except InvalidOperation as error:
        raise DecimalParseError(f"invalid decimal value '{raw}'") from error


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
