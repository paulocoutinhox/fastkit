import pytest

from helpers.text import alphabetical, is_valid_cpf, only_digits, slugify


@pytest.mark.parametrize("value,expected", [("Hello World", "hello-world"), ("Ação & Reação", "acao-reacao"), ("  ---  ", "item"), ("", "item")])
def test_slugify(value, expected):
    assert slugify(value) == expected


def test_slugify_uses_the_given_fallback():
    assert slugify("!!!", "tenant") == "tenant"


def test_slugify_cuts_to_the_length_it_is_given():
    assert slugify("a very long title that will not fit", "item", 10) == "a-very-lon"


def test_slugify_never_ends_on_a_separator():
    assert slugify("one two three", "item", 8) == "one-two"


def test_slugify_falls_back_when_the_cut_leaves_nothing():
    assert slugify("anything", "item", 0) == "item"


@pytest.mark.parametrize("value,expected", [("123.456-78", "12345678"), (None, ""), ("abc", "")])
def test_only_digits(value, expected):
    assert only_digits(value) == expected


@pytest.mark.parametrize("value", ["529.982.247-25", "52998224725"])
def test_valid_cpf(value):
    assert is_valid_cpf(value) is True


@pytest.mark.parametrize("value", [None, "", "11111111111", "12345678900", "123", "5299822472"])
def test_invalid_cpf(value):
    assert is_valid_cpf(value) is False


def test_alphabetical_ignores_accents_and_case():
    assert sorted(["Zebra", "Ébano", "ebook", "Abacate"], key=alphabetical) == ["Abacate", "Ébano", "ebook", "Zebra"]


def test_alphabetical_reads_a_run_of_digits_as_a_number():
    assert sorted(["item 10", "item 2", "item 1"], key=alphabetical) == ["item 1", "item 2", "item 10"]


def test_alphabetical_orders_a_number_before_a_word():
    assert sorted(["b", "2"], key=alphabetical) == ["2", "b"]


def test_alphabetical_accepts_nothing():
    assert alphabetical(None) == ()
