import pytest_asyncio

from fastkit_core.app_config import CoreApp
from fastkit_core.runtime import Runtime
from fastkit_i18n.app import I18nApp
from fastkit_i18n.jinja import install_i18n
from fastkit_i18n.locale import (
    base_of,
    fallback_chain,
    get_locale,
    normalize,
    parse_accept_language,
    reset_locale,
    set_locale,
)
from fastkit_i18n.resolver import LocaleResolver
from fastkit_i18n.translator import Translator


def test_normalize_and_base():
    assert normalize("pt-br") == "pt_BR"
    assert normalize("EN") == "en"
    assert base_of("pt_BR") == "pt"


def test_fallback_chain():
    assert fallback_chain("pt-BR", ["pt_BR", "pt", "en"], "en") == ["pt_BR", "pt", "en"]
    assert fallback_chain("es_MX", ["es", "en"], "en") == ["es", "en"]
    assert fallback_chain("de", ["pt", "en"], "en") == ["en"]


def test_parse_accept_language():
    result = parse_accept_language("pt-BR,pt;q=0.9,en;q=0.5")

    assert result == ["pt_BR", "pt", "en"]
    assert parse_accept_language(" , ") == []


def test_parse_accept_language_skips_malformed_quality():
    assert parse_accept_language("en;q=high,pt;q=0.9") == ["pt"]


def test_locale_contextvar():
    assert get_locale() == "en"
    token = set_locale("pt_BR")

    try:
        assert get_locale() == "pt_BR"
    finally:
        reset_locale(token)

    assert get_locale() == "en"


def test_translator_lookup_and_fallback():
    translator = Translator(
        {"en": {"a": "A"}, "pt": {"a": "Aa"}},
        supported=["en", "pt"],
        default_locale="en",
    )

    assert translator.gettext("a", locale="pt") == "Aa"
    assert translator.gettext("a", locale="pt_BR") == "Aa"
    assert translator.gettext("missing", locale="pt") == "missing"


def test_translator_params_and_plural():
    translator = Translator(
        {"en": {"hello": "Hello {name}", "one": "1 item", "many": "{count} items"}},
        supported=["en"],
        default_locale="en",
    )

    assert translator.gettext("hello", locale="en", name="Ada") == "Hello Ada"
    assert translator.ngettext("one", "many", 1, locale="en") == "1 item"
    assert translator.ngettext("one", "many", 5, locale="en") == "5 items"


def test_translator_activate_and_add_catalog():
    translator = Translator({}, supported=["en", "pt"], default_locale="en")
    translator.add_catalog("pt", {"k": "valor"})

    with translator.activate("pt"):
        assert get_locale() == "pt"
        assert translator.gettext("k") == "valor"

    assert get_locale() == "en"


def test_translator_add_new_locale_registers_and_resolves():
    translator = Translator(
        {"en": {"k": "value"}}, supported=["en"], default_locale="en"
    )

    # a locale that was never declared can be added at runtime
    translator.add_catalog("de", {"k": "Wert"})

    assert "de" in translator.supported()
    assert translator.gettext("k", locale="de") == "Wert"
    # unknown keys fall back to the default locale
    translator.add_catalog("en", {"only_en": "English"})
    assert translator.gettext("only_en", locale="de") == "English"


def test_gettext_lenient_formatting_never_crashes():
    translator = Translator(
        {"en": {"a": "Hi {name}", "b": "Raw brace {"}},
        supported=["en"],
        default_locale="en",
    )

    assert translator.gettext("a", locale="en", other="x") == "Hi {name}"
    assert translator.gettext("b", locale="en", x=1) == "Raw brace {"


def test_base_catalogs_are_key_symmetric():
    from fastkit_i18n.catalogs import BASE_CATALOGS

    english = set(BASE_CATALOGS["en"])

    for locale, catalog in BASE_CATALOGS.items():
        assert set(catalog) == english, (
            f"{locale} catalog keys differ from en: {english.symmetric_difference(catalog)}"
        )


def test_translator_messages_merges_fallback_chain():
    translator = Translator(
        {"en": {"a": "A", "b": "B"}, "pt": {"a": "Aa"}},
        supported=["en", "pt"],
        default_locale="en",
    )

    messages = translator.messages("pt_BR")

    # own keys win, missing keys inherited from the fallback chain
    assert messages["a"] == "Aa"
    assert messages["b"] == "B"


def test_resolver_order():
    supported = ["en", "pt", "es"]
    resolver = LocaleResolver(supported=lambda: supported, default_locale="en")

    assert resolver.resolve(user_locale="pt") == "pt"
    assert resolver.resolve(user_locale="de", tenant_locale="es") == "es"
    assert resolver.resolve(cookie_locale="pt") == "pt"
    assert resolver.resolve(accept_language="fr,es;q=0.9") == "es"
    assert resolver.resolve(accept_language="fr,de") == "en"
    assert resolver.resolve() == "en"
    assert resolver.resolve(user_locale="unsupported") == "en"


def test_registering_a_new_locale_makes_it_resolvable():
    translator = Translator(
        {"en": {"error.internal": "Oops"}}, supported=["en"], default_locale="en"
    )
    resolver = LocaleResolver(supported=translator.supported, default_locale="en")

    assert resolver.resolve(user_locale="de") == "en"

    translator.add_catalog("de", {"error.internal": "Hoppla"})

    assert resolver.resolve(user_locale="de") == "de"


def test_jinja_integration():
    class FakeEnv:
        def __init__(self):
            self.globals = {}

    translator = Translator(
        {"en": {"admin.save": "Save"}}, supported=["en"], default_locale="en"
    )
    env = FakeEnv()
    install_i18n(env, translator)

    assert env.globals["_"]("admin.save", locale="en") == "Save"
    assert "ngettext" in env.globals


class Settings:
    class i18n:
        default_locale = "en"
        supported_locales = ["en", "pt", "es"]

    installed_apps = ["fastkit.core", "fastkit.i18n"]


@pytest_asyncio.fixture
async def runtime(monkeypatch):
    monkeypatch.setattr(
        "fastkit_core.runtime.discover_apps",
        lambda: {"fastkit.core": CoreApp, "fastkit.i18n": I18nApp},
    )
    runtime = Runtime(settings=Settings(), installed_apps=list(Settings.installed_apps))
    runtime.bootstrap()

    yield runtime

    await runtime.stop()


async def test_i18n_app_registers(runtime):
    translator = runtime.component("translator")
    resolver = runtime.component("locale_resolver")

    assert (
        translator.gettext("error.not-found", locale="pt")
        == "O recurso solicitado não foi encontrado."
    )
    assert resolver.resolve(user_locale="pt") == "pt"

    translator.add_catalog("de", {"error.internal": "Hoppla"})

    assert resolver.resolve(user_locale="de") == "de"
