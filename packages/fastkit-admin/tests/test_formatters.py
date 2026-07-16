from datetime import date, datetime
from decimal import Decimal

import pytest

from fastkit_admin.formatters import (
    DecimalParseError,
    format_date,
    format_datetime,
    format_decimal,
    locale_format,
    parse_date,
    parse_datetime,
    parse_decimal,
)


def test_format_decimal_en():
    assert format_decimal(Decimal("1234567.5"), "en") == "1,234,567.50"


def test_format_decimal_pt():
    assert format_decimal(Decimal("1234567.5"), "pt") == "1.234.567,50"
    assert format_decimal(Decimal("1234567.5"), "pt_BR") == "1.234.567,50"


def test_format_decimal_negative_and_zero_places():
    assert format_decimal(Decimal("-1234.5"), "pt") == "-1.234,50"
    assert format_decimal(Decimal("1234"), "en", decimal_places=0) == "1,234"


def test_format_decimal_small():
    assert format_decimal(Decimal("5.5"), "en") == "5.50"


def test_parse_decimal_variants():
    assert parse_decimal("1.234.567,50", "pt") == Decimal("1234567.50")
    assert parse_decimal("1,234,567.50", "en") == Decimal("1234567.50")
    assert parse_decimal("1234.5", "en") == Decimal("1234.5")
    assert parse_decimal(Decimal("3"), "en") == Decimal("3")
    assert parse_decimal(5, "en") == Decimal("5")
    assert parse_decimal(5.5, "en") == Decimal("5.5")


def test_parse_decimal_errors():
    with pytest.raises(DecimalParseError):
        parse_decimal("", "en")

    with pytest.raises(DecimalParseError):
        parse_decimal("abc", "en")


def test_date_formatting():
    assert format_date(date(2026, 7, 14), "en") == "07/14/2026"
    assert format_date(date(2026, 7, 14), "pt") == "14/07/2026"


def test_datetime_formatting():
    assert format_datetime(datetime(2026, 7, 14, 9, 5), "pt") == "14/07/2026 09:05"


def test_parse_date_variants():
    assert parse_date("2026-07-14", "en") == date(2026, 7, 14)
    assert parse_date("14/07/2026", "pt") == date(2026, 7, 14)

    with pytest.raises(ValueError):
        parse_date("not-a-date", "en")


def test_parse_datetime_variants():
    assert parse_datetime("2026-07-14T09:05", "en") == datetime(2026, 7, 14, 9, 5)
    assert parse_datetime("2026-07-14 09:05:30", "en") == datetime(2026, 7, 14, 9, 5, 30)
    assert parse_datetime("14/07/2026 09:05", "pt") == datetime(2026, 7, 14, 9, 5)

    with pytest.raises(ValueError):
        parse_datetime("nope", "en")


def test_locale_format_fallback():
    assert locale_format("de") is locale_format("en")


def test_time_formatting():
    from datetime import time

    from fastkit_admin.formatters import format_time, parse_time

    assert format_time(time(9, 5), "en") == "09:05"
    assert parse_time("09:05") == time(9, 5)
    assert parse_time("09:05:30") == time(9, 5, 30)

    with pytest.raises(ValueError):
        parse_time("not-a-time")
