from datetime import datetime, timedelta, timezone

import pytest

from helpers.dates import add_interval, add_months, as_utc, naive_utc, now


def test_now_is_aware_and_utc():
    assert now().tzinfo == timezone.utc


def test_as_utc_reads_a_naive_value_as_utc():
    assert as_utc(datetime(2026, 1, 1, 12)) == datetime(2026, 1, 1, 12, tzinfo=timezone.utc)


def test_as_utc_converts_an_offset():
    value = datetime(2026, 1, 1, 12, tzinfo=timezone(timedelta(hours=-3)))

    assert as_utc(value) == datetime(2026, 1, 1, 15, tzinfo=timezone.utc)


def test_as_utc_keeps_none():
    assert as_utc(None) is None
    assert naive_utc(None) is None


def test_naive_utc_drops_the_offset():
    value = datetime(2026, 1, 1, 12, tzinfo=timezone(timedelta(hours=-3)))

    assert naive_utc(value) == datetime(2026, 1, 1, 15)


def test_add_months_clamps_to_the_last_day():
    assert add_months(datetime(2026, 1, 31), 1) == datetime(2026, 2, 28)


def test_add_months_rolls_the_year():
    assert add_months(datetime(2026, 12, 15), 2) == datetime(2027, 2, 15)


@pytest.mark.parametrize("unit,value,expected", [("day", 3, datetime(2026, 1, 4)), ("week", 2, datetime(2026, 1, 15)), ("month", 1, datetime(2026, 2, 1)), ("year", 1, datetime(2027, 1, 1))])
def test_add_interval(unit, value, expected):
    assert add_interval(datetime(2026, 1, 1), unit, value) == expected
