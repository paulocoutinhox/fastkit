from decimal import Decimal, InvalidOperation

from fastkit_admin.formatters.errors import DecimalParseError
from fastkit_admin.formatters.locale_format import locale_format


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
