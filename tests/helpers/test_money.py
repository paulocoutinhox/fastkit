"""A gateway is told a whole number of the smallest unit its currency has, and how small that is belongs to the currency."""

from decimal import Decimal

import pytest

from helpers.money import factor, from_minor_units, minor_units


@pytest.mark.parametrize("currency,expected", [("USD", 100), ("usd", 100), ("BRL", 100), ("JPY", 1), ("KRW", 1), ("KWD", 1000), ("bhd", 1000)])
def test_a_currency_says_how_small_its_smallest_unit_is(currency, expected):
    assert factor(currency) == expected


@pytest.mark.parametrize("amount,currency,expected", [("19.90", "USD", 1990), ("19.90", "JPY", 20), ("19.90", "KWD", 19900), ("0.01", "USD", 1), ("1000.00", "BRL", 100000)])
def test_an_amount_is_charged_in_the_units_of_its_own_currency(amount, currency, expected):
    assert minor_units(Decimal(amount), currency) == expected


def test_a_price_a_currency_cannot_hold_is_rounded_and_never_cut_short():
    """A catalogue keeps two decimals whatever the currency does, and truncating one that keeps none charges less than the page said."""
    assert minor_units(Decimal("19.99"), "JPY") == 20
    assert minor_units(Decimal("19.49"), "JPY") == 19
    assert minor_units(Decimal("19.50"), "JPY") == 20


@pytest.mark.parametrize("amount,currency,expected", [(1990, "USD", "19.90"), (20, "JPY", "20"), (19900, "KWD", "19.90")])
def test_what_a_gateway_answered_reads_back_as_the_amount_it_was(amount, currency, expected):
    assert from_minor_units(amount, currency) == Decimal(expected)


@pytest.mark.parametrize("currency", ["USD", "KWD"])
def test_the_two_readings_answer_each_other(currency):
    """A currency that holds the amount reads it back whole, and one that holds fewer decimals was already rounded on the way out."""
    assert from_minor_units(minor_units(Decimal("19.90"), currency), currency) == Decimal("19.90")


def test_every_column_that_holds_money_holds_what_the_finest_currency_divides_into():
    """The helper knows a dinar divides into thousandths, and a column of two decimals rounds that away without a word."""
    import models.registry  # noqa

    from helpers.db import Base
    from helpers.money import THREE_DECIMAL, factor

    finest = max(len(str(factor(currency))) - 1 for currency in THREE_DECIMAL)
    narrow = []
    counted = 0

    for mapper in Base.registry.mappers:
        for column in mapper.class_.__table__.columns:
            if type(column.type).__name__ != "Numeric":
                continue

            counted += 1

            if (column.type.scale or 0) < finest:
                narrow.append(f"{mapper.class_.__name__}.{column.name} keeps {column.type.scale} decimals and a currency divides into {finest}")

    assert counted >= 5, "the guard read too few columns to claim anything"
    assert narrow == []
