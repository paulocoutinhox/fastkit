from datetime import datetime, timezone

from sqlalchemy import select

from fastkit_core.errors.codes import RESOURCE_NOT_FOUND
from fastkit_core.errors.exceptions import NotFoundError
from fastkit_i18n.locale import fallback_chain
from fastkit_content.models import (
    Content,
    ContentStatus,
    ContentTranslation,
    ContentType,
    Language,
)
from fastkit_core.sanitize import sanitize_html
from fastkit_tenancy.constants import to_api, to_persisted

SEED_LANGUAGES = (
    {"code": "en", "name": "English", "native_name": "English", "is_default": True},
    {"code": "pt", "name": "Portuguese", "native_name": "Português", "is_default": False},
    {"code": "es", "name": "Spanish", "native_name": "Español", "is_default": False},
)

_SANITIZED_TYPES = frozenset({ContentType.rich_text.value, ContentType.html.value})


class LanguageService:
    """Manages the Language catalog and guarantees a single default language."""

    def __init__(self, database):
        self._database = database

    async def seed_defaults(self) -> int:
        created = 0

        async with self._database.session_factory() as session:
            for entry in SEED_LANGUAGES:
                existing = (await session.execute(select(Language).where(Language.code == entry["code"]))).scalar_one_or_none()

                if existing is None:
                    session.add(Language(code=entry["code"], base_code=entry["code"], name=entry["name"], native_name=entry["native_name"], is_default=entry["is_default"], is_system=True))
                    created += 1

            await session.commit()

        return created

    async def list_active(self) -> list[Language]:
        async with self._database.session_factory() as session:
            result = await session.execute(select(Language).where(Language.is_active.is_(True)).order_by(Language.sort_order))

            return list(result.scalars().all())

    async def get_by_code(self, code: str) -> Language | None:
        async with self._database.session_factory() as session:
            return (await session.execute(select(Language).where(Language.code == code))).scalar_one_or_none()

    async def set_default(self, code: str) -> None:
        async with self._database.session_factory() as session:
            languages = (await session.execute(select(Language))).scalars().all()

            for language in languages:
                language.is_default = language.code == code

            await session.commit()

    async def create(self, code: str, name: str, native_name: str, direction: str = "ltr") -> Language:
        async with self._database.session_factory() as session:
            language = Language(code=code, base_code=code.split("_")[0], name=name, native_name=native_name, direction=direction)
            session.add(language)
            await session.commit()
            await session.refresh(language)

            return language


class ContentService:
    """Stores and resolves translatable content, sanitizing rich HTML on write."""

    def __init__(self, database):
        self._database = database

    async def ensure_content(self, key: str, tenant_id: int | None = None, content_type: str = ContentType.rich_text.value) -> Content:
        persisted = to_persisted(tenant_id)

        async with self._database.session_factory() as session:
            content = (await session.execute(select(Content).where(Content.tenant_id == persisted, Content.key == key))).scalar_one_or_none()

            if content is None:
                content = Content(tenant_id=persisted, key=key, type=content_type)
                session.add(content)
                await session.commit()
                await session.refresh(content)

            return content

    async def set_translation(self, content_id, language_id, title: str | None = None, summary: str | None = None, body: str | None = None) -> ContentTranslation:
        async with self._database.session_factory() as session:
            content = await self._require_content(session, content_id)
            clean_body = sanitize_html(body) if body is not None and content.type in _SANITIZED_TYPES else body

            translation = (
                await session.execute(select(ContentTranslation).where(ContentTranslation.content_id == content_id, ContentTranslation.language_id == language_id))
            ).scalar_one_or_none()

            if translation is None:
                translation = ContentTranslation(content_id=content_id, language_id=language_id, title=title, summary=summary, body=clean_body)
                session.add(translation)
            else:
                translation.title = title
                translation.summary = summary
                translation.body = clean_body
                translation.version += 1

            await session.commit()
            await session.refresh(translation)

            return translation

    async def publish(self, content_id) -> Content:
        async with self._database.session_factory() as session:
            content = await self._require_content(session, content_id)
            content.status = ContentStatus.published.value
            content.published_at = datetime.now(timezone.utc)
            await session.commit()
            await session.refresh(content)

            return content

    async def _require_content(self, session, content_id) -> Content:
        content = await session.get(Content, content_id)

        if content is None:
            raise NotFoundError(RESOURCE_NOT_FOUND, message="content not found")

        return content

    async def translations(self, key: str, tenant_id: int | None = None) -> list[dict]:
        persisted = to_persisted(tenant_id)

        async with self._database.session_factory() as session:
            content = (await session.execute(select(Content).where(Content.tenant_id == persisted, Content.key == key))).scalar_one_or_none()

            if content is None:
                return []

            rows = (
                await session.execute(
                    select(ContentTranslation, Language.code)
                    .join(Language, Language.id == ContentTranslation.language_id)
                    .where(ContentTranslation.content_id == content.id)
                    .order_by(Language.sort_order, Language.code)
                )
            ).all()

            return [{"language": code, "title": translation.title, "summary": translation.summary, "body": translation.body} for translation, code in rows]

    async def translations_by_content_id(self, content_id) -> list[dict]:
        async with self._database.session_factory() as session:
            content = await session.get(Content, content_id)

        if content is None:
            return []

        return await self.translations(content.key, tenant_id=to_api(content.tenant_id))

    async def get(self, key: str, locale: str | None = None, tenant_id: int | None = None, supported: list[str] | None = None, default_locale: str = "en") -> str | None:
        persisted = to_persisted(tenant_id)

        async with self._database.session_factory() as session:
            content = (await session.execute(select(Content).where(Content.tenant_id == persisted, Content.key == key))).scalar_one_or_none()

            if content is None:
                return None

            if locale is None:
                locale = await self._default_locale(session, content, default_locale)

            codes = fallback_chain(locale, supported or [locale, default_locale], default_locale)

            for code in codes:
                language = (await session.execute(select(Language).where(Language.code == code))).scalar_one_or_none()

                if language is None:
                    continue

                translation = (
                    await session.execute(select(ContentTranslation).where(ContentTranslation.content_id == content.id, ContentTranslation.language_id == language.id))
                ).scalar_one_or_none()

                if translation is not None and translation.body is not None:
                    return translation.body

            return None

    async def _default_locale(self, session, content, default_locale: str) -> str:
        if content.default_language_id is not None:
            language = await session.get(Language, content.default_language_id)

            if language is not None:
                return language.code

        system_default = (await session.execute(select(Language).where(Language.is_default.is_(True)))).scalar_one_or_none()

        return system_default.code if system_default is not None else default_locale
