"""An amount is charged in the smallest unit of its currency and read in the way of whoever is reading it, which are two different questions."""

from decimal import Decimal

import pytest

from helpers.money import money, number, places


@pytest.mark.parametrize("locale, written", [("en", "1,234,567"), ("pt", "1.234.567"), ("es", "1.234.567")])
def test_a_number_is_grouped_the_way_the_language_groups_one(locale, written):
    assert number(1234567, locale) == written


@pytest.mark.parametrize("locale, written", [("en", "1,234.50"), ("pt", "1.234,50"), ("es", "1.234,50")])
def test_a_decimal_carries_the_point_of_the_language(locale, written):
    assert number(Decimal("1234.5"), locale, 2) == written


def test_a_negative_number_keeps_its_sign_in_front_of_the_grouping():
    assert number(Decimal("-1234.5"), "pt", 2) == "-1.234,50"


@pytest.mark.parametrize("locale, written", [("en", "$1,234.50"), ("pt", "$ 1.234,50"), ("es", "1.234,50 $")])
def test_a_symbol_sits_where_the_language_puts_it(locale, written):
    assert money(Decimal("1234.5"), "USD", locale, "$") == written


@pytest.mark.parametrize("locale, written", [("en", "USD 1.00"), ("pt", "USD 1,00"), ("es", "1,00 USD")])
def test_a_code_keeps_its_space_because_it_is_a_word_and_not_a_mark(locale, written):
    assert money(Decimal("1"), "USD", locale) == written


def test_an_amount_carries_the_decimals_its_own_currency_divides_into():
    """A yen has none and a dinar has three, so writing two everywhere states a precision the currency does not have."""
    assert places("jpy") == 0
    assert places("usd") == 2
    assert places("kwd") == 3
    assert money(Decimal("1234"), "JPY", "en") == "JPY 1,234"
    assert money(Decimal("1.234"), "KWD", "en") == "KWD 1.234"


def test_every_language_this_instance_offers_says_how_it_writes_a_number():
    """A language added without a format would read as English, which is a wrong number shown to somebody who cannot tell."""
    from helpers.money import GROUPING, PLACEMENT
    from helpers.settings import settings

    assert sorted(GROUPING) == sorted(settings.supported_languages)
    assert sorted(PLACEMENT) == sorted(settings.supported_languages)


def test_a_language_nobody_offers_never_reaches_the_formatter():
    """The locale is resolved against what this instance offers, so an undeclared one is a name written by mistake."""
    with pytest.raises(KeyError):
        money(Decimal("1.5"), "USD", "de", "$")
