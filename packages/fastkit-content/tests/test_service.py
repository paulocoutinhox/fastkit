import pytest_asyncio

from fastkit_core.app_config import CoreApp
from fastkit_core.runtime import Runtime
from fastkit_db.app import DbApp
from fastkit_i18n.app import I18nApp
from fastkit_content.app import ContentApp
from fastkit_content.models import Content, ContentStatus, ContentType
from fastkit_content.service import ContentService, LanguageService


async def test_seed_languages_is_idempotent(languages):
    assert await languages.seed_defaults() == 3
    assert await languages.seed_defaults() == 0

    active = await languages.list_active()
    assert {language.code for language in active} == {"en", "pt", "es"}
    assert sum(1 for language in active if language.is_default) == 1


async def test_get_by_code_and_create(languages):
    await languages.seed_defaults()

    assert (await languages.get_by_code("pt")).native_name == "Português"
    assert await languages.get_by_code("de") is None

    created = await languages.create("fr", "French", "Français")
    assert created.base_code == "fr"


async def test_set_default_moves_flag(languages):
    await languages.seed_defaults()
    await languages.set_default("pt")

    active = await languages.list_active()
    defaults = [language.code for language in active if language.is_default]

    assert defaults == ["pt"]


async def test_content_mutators_reject_a_missing_content(content):
    import pytest

    from fastkit_core.errors.exceptions import NotFoundError

    with pytest.raises(NotFoundError):
        await content.set_translation(999999, 1, title="x")

    with pytest.raises(NotFoundError):
        await content.publish(999999)


async def test_content_translation_and_fallback(languages, content):
    await languages.seed_defaults()

    node = await content.ensure_content("home.hero", tenant_id=1)
    same = await content.ensure_content("home.hero", tenant_id=1)
    assert node.id == same.id

    en = await languages.get_by_code("en")
    pt = await languages.get_by_code("pt")

    await content.set_translation(node.id, en.id, title="Hero", body="<p>Welcome</p>")
    await content.set_translation(node.id, pt.id, title="Hero", body="<p>Bem-vindo</p>")

    assert (
        await content.get("home.hero", "pt_BR", tenant_id=1, supported=["en", "pt"])
        == "<p>Bem-vindo</p>"
    )
    assert (
        await content.get("home.hero", "es", tenant_id=1, supported=["en", "pt", "es"])
        == "<p>Welcome</p>"
    )


async def test_get_without_locale_uses_default_language(languages, content):
    await languages.seed_defaults()

    node = await content.ensure_content("home.title", tenant_id=1)
    en = await languages.get_by_code("en")
    pt = await languages.get_by_code("pt")
    await content.set_translation(node.id, en.id, body="<p>Default</p>")
    await content.set_translation(node.id, pt.id, body="<p>Padrão</p>")

    assert await content.get("home.title", tenant_id=1) == "<p>Default</p>"
    assert await content.get("missing.key", tenant_id=1) is None


async def test_get_honours_content_default_language(languages, content, database):
    from fastkit_content.models import Content

    await languages.seed_defaults()
    node = await content.ensure_content("promo", tenant_id=1)
    en = await languages.get_by_code("en")
    pt = await languages.get_by_code("pt")
    await content.set_translation(node.id, en.id, body="<p>en</p>")
    await content.set_translation(node.id, pt.id, body="<p>pt</p>")

    async with database.session_factory() as session:
        stored = await session.get(Content, node.id)
        stored.default_language_id = pt.id
        await session.commit()

    assert await content.get("promo", tenant_id=1) == "<p>pt</p>"

    async with database.session_factory() as session:
        stored = await session.get(Content, node.id)
        stored.default_language_id = 999999
        await session.commit()

    # a dangling default language falls back to the system default language
    assert await content.get("promo", tenant_id=1) == "<p>en</p>"


async def test_get_falls_back_to_default_locale_without_default_language(
    languages, content, database
):
    from sqlalchemy import update

    from fastkit_content.models import Language

    await languages.seed_defaults()
    node = await content.ensure_content("plain", tenant_id=1)
    en = await languages.get_by_code("en")
    await content.set_translation(node.id, en.id, body="<p>fallback</p>")

    async with database.session_factory() as session:
        await session.execute(update(Language).values(is_default=False))
        await session.commit()

    assert (
        await content.get("plain", tenant_id=1, default_locale="en")
        == "<p>fallback</p>"
    )


async def test_translations_by_content_id(languages, content):
    await languages.seed_defaults()
    node = await content.ensure_content("page.about", tenant_id=1)
    en = await languages.get_by_code("en")
    await content.set_translation(node.id, en.id, title="About", body="<p>About us</p>")

    rows = await content.translations_by_content_id(node.id)
    assert rows[0]["language"] == "en"
    assert rows[0]["body"] == "<p>About us</p>"
    assert await content.translations_by_content_id(999999) == []


async def test_translations_lists_every_language(languages, content):
    await languages.seed_defaults()

    node = await content.ensure_content("home.body", tenant_id=1)
    en = await languages.get_by_code("en")
    pt = await languages.get_by_code("pt")
    await content.set_translation(node.id, en.id, title="Body", body="<p>en</p>")
    await content.set_translation(node.id, pt.id, title="Corpo", body="<p>pt</p>")

    rows = await content.translations("home.body", tenant_id=1)
    by_language = {row["language"]: row for row in rows}

    assert by_language["en"]["body"] == "<p>en</p>"
    assert by_language["pt"]["title"] == "Corpo"
    assert await content.translations("missing", tenant_id=1) == []


async def test_set_translation_sanitizes_rich_html(languages, content):
    await languages.seed_defaults()
    node = await content.ensure_content(
        "page.body", tenant_id=1, content_type=ContentType.rich_text.value
    )
    en = await languages.get_by_code("en")

    translation = await content.set_translation(
        node.id, en.id, body="<p>ok</p><script>alert(1)</script>"
    )

    assert "script" not in translation.body
    assert "<p>ok</p>" in translation.body


async def test_plain_text_is_not_sanitized(languages, content):
    await languages.seed_defaults()
    node = await content.ensure_content(
        "raw", tenant_id=1, content_type=ContentType.plain_text.value
    )
    en = await languages.get_by_code("en")

    translation = await content.set_translation(node.id, en.id, body="1 < 2")

    assert translation.body == "1 < 2"


async def test_update_translation_bumps_version(languages, content):
    await languages.seed_defaults()
    node = await content.ensure_content("v", tenant_id=1)
    en = await languages.get_by_code("en")

    first = await content.set_translation(node.id, en.id, body="<p>a</p>")
    second = await content.set_translation(node.id, en.id, body="<p>b</p>")

    assert first.version == 1
    assert second.version == 2


async def test_publish(languages, content):
    node = await content.ensure_content("p", tenant_id=1)

    published = await content.publish(node.id)

    assert published.status == ContentStatus.published.value
    assert published.published_at is not None


async def test_get_missing_content(content):
    assert await content.get("nope", "en", tenant_id=1) is None


async def test_get_without_translation_returns_none(languages, content):
    await languages.seed_defaults()
    await content.ensure_content("empty", tenant_id=1)

    assert await content.get("empty", "en", tenant_id=1, supported=["en"]) is None


async def test_get_skips_unknown_language_in_chain(languages, content):
    # only english is seeded, but the fallback chain includes an unmapped locale
    await languages.create("en", "English", "English")
    node = await content.ensure_content("k", tenant_id=1)
    en = await languages.get_by_code("en")
    await content.set_translation(node.id, en.id, body="<p>hi</p>")

    assert (
        await content.get("k", "de", tenant_id=1, supported=["de", "en"]) == "<p>hi</p>"
    )


class Settings:
    class database:
        url = "sqlite+aiosqlite:///:memory:"
        pool_pre_ping = True
        pool_recycle = 1800
        echo = False

    class i18n:
        default_locale = "en"
        supported_locales = ["en", "pt", "es"]

    installed_apps = ["fastkit.core", "fastkit.db", "fastkit.i18n", "fastkit.content"]


@pytest_asyncio.fixture
async def runtime(monkeypatch):
    monkeypatch.setattr(
        "fastkit_core.runtime.discover_apps",
        lambda: {
            "fastkit.core": CoreApp,
            "fastkit.db": DbApp,
            "fastkit.i18n": I18nApp,
            "fastkit.content": ContentApp,
        },
    )
    runtime = Runtime(settings=Settings(), installed_apps=list(Settings.installed_apps))
    runtime.bootstrap()

    yield runtime

    await runtime.stop()


async def test_content_app_registers(runtime):
    assert Content in runtime.models.all()
    assert isinstance(runtime.component("content_service"), ContentService)
    assert isinstance(runtime.component("language_service"), LanguageService)


def test_language_and_content_display_label():
    from fastkit_content.models import Content, Language

    assert Language(name="Portuguese").display_label() == "Portuguese"
    assert Content(key="home.title").display_label() == "home.title"
