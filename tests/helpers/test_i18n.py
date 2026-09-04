import pytest

from helpers.errors import validation_message
from helpers.i18n import catalogs, current_locale, resolve_locale, translate


def test_every_supported_catalog_holds_the_same_keys():
    reference = set(catalogs["en"])

    for language, catalog in catalogs.items():
        assert set(catalog) == reference, f"the {language} catalog drifted"


@pytest.mark.parametrize("header,expected", [("pt-BR,pt;q=0.9", "pt"), ("en-US", "en"), ("fr", "en"), (None, "en"), ("", "en"), (",;", "en"), ("pt", "pt")])
def test_resolve_locale(header, expected):
    assert resolve_locale(header) == expected


def test_translate_answers_in_the_current_locale():
    token = current_locale.set("pt")

    try:
        assert translate("error.not-found") == "O registro solicitado não foi encontrado."
    finally:
        current_locale.reset(token)


def test_translate_accepts_an_explicit_locale():
    assert translate("error.not-found", "en") == "The requested record was not found."


def test_translate_interpolates_parameters():
    assert "3" in translate("validation.string-too-short", "en", min_length=3)


def test_a_blank_field_is_told_it_is_blank_and_not_a_length():
    """Asking for at least one character is asking for something rather than nothing, and "at least 1 characters" says neither well."""
    blank = validation_message({"type": "string_too_short", "ctx": {"min_length": 1}})
    short = validation_message({"type": "string_too_short", "ctx": {"min_length": 3}})

    assert blank == translate("validation.blank", "en")
    assert "3" in short and blank != short


def test_translate_answers_the_key_when_it_is_unknown():
    assert translate("error.does-not-exist", "en") == "error.does-not-exist"
