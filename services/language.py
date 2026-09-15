from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from helpers.settings import settings
from models.language import Language
from services.crud import CrudService


class LanguageService(CrudService):
    model = Language
    system_wide = True
    search_fields = ("code_iso_639_1", "code_iso_language")
    text_search_fields = ("name", "native_name")
    filter_fields = ("active",)
    ordering_fields = ("id", "name", "code_iso_639_1", "created_at")
    default_ordering = "name"
    label_fields = ("name",)

    async def find_by_code(self, db: AsyncSession, code: str) -> Language | None:
        """The row behind a two letter code, which is what the site has when somebody picks a language off the footer."""
        return await db.scalar(select(Language).where(Language.code_iso_639_1 == code.lower(), Language.active.is_(True)))

    async def offered(self, db: AsyncSession) -> list[Language]:
        """The rows behind the languages this instance offers, in the order the configuration names them."""
        found = {row.code_iso_639_1: row for row in await db.scalars(select(Language).where(Language.code_iso_639_1.in_(list(settings.languages)), Language.active.is_(True)))}

        return [found[code] for code in settings.languages if code in found]

    async def prepare(self, data: dict, instance) -> dict:
        prepared = dict(data)

        for name in ("code_iso_639_1", "code_iso_language"):
            if prepared.get(name):
                prepared[name] = prepared[name].lower()

        return prepared

    async def validate(self, db: AsyncSession, data: dict, instance) -> None:
        code = data.get("code_iso_639_1")

        if code:
            await self.ensure_unique(db, Language.code_iso_639_1, code.lower(), "error.code-already-used", "code_iso_639_1", instance)


language_service = LanguageService()
