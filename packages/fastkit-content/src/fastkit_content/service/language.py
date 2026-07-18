from sqlalchemy import select

from fastkit_content.models import Language

SEED_LANGUAGES = (
    {"code": "en", "name": "English", "native_name": "English", "is_default": True},
    {
        "code": "pt",
        "name": "Portuguese",
        "native_name": "Português",
        "is_default": False,
    },
    {"code": "es", "name": "Spanish", "native_name": "Español", "is_default": False},
)


class LanguageService:
    """Manages the Language catalog and guarantees a single default language."""

    def __init__(self, database):
        self._database = database

    async def seed_defaults(self) -> int:
        created = 0

        async with self._database.session_factory() as session:
            for entry in SEED_LANGUAGES:
                existing = (
                    await session.execute(
                        select(Language).where(Language.code == entry["code"])
                    )
                ).scalar_one_or_none()

                if existing is None:
                    session.add(
                        Language(
                            code=entry["code"],
                            base_code=entry["code"],
                            name=entry["name"],
                            native_name=entry["native_name"],
                            is_default=entry["is_default"],
                            is_system=True,
                        )
                    )
                    created += 1

            await session.commit()

        return created

    async def list_active(self) -> list[Language]:
        async with self._database.session_factory() as session:
            result = await session.execute(
                select(Language)
                .where(Language.is_active.is_(True))
                .order_by(Language.sort_order)
            )

            return list(result.scalars().all())

    async def get_by_code(self, code: str) -> Language | None:
        async with self._database.session_factory() as session:
            return (
                await session.execute(select(Language).where(Language.code == code))
            ).scalar_one_or_none()

    async def set_default(self, code: str) -> None:
        async with self._database.session_factory() as session:
            languages = (await session.execute(select(Language))).scalars().all()

            for language in languages:
                language.is_default = language.code == code

            await session.commit()

    async def create(
        self, code: str, name: str, native_name: str, direction: str = "ltr"
    ) -> Language:
        async with self._database.session_factory() as session:
            language = Language(
                code=code,
                base_code=code.split("_")[0],
                name=name,
                native_name=native_name,
                direction=direction,
            )
            session.add(language)
            await session.commit()
            await session.refresh(language)

            return language
