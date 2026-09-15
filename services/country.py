from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.country import Country
from services.crud import CrudService


class CountryService(CrudService):
    model = Country
    system_wide = True
    search_fields = ("code_iso_3166_1",)
    text_search_fields = ("name",)
    filter_fields = ("active", "postal_code_provider")
    ordering_fields = ("id", "name", "code_iso_3166_1", "created_at")
    default_ordering = "name"
    label_fields = ("name",)

    async def prepare(self, data: dict, instance) -> dict:
        prepared = dict(data)

        if prepared.get("code_iso_3166_1"):
            prepared["code_iso_3166_1"] = prepared["code_iso_3166_1"].upper()

        return prepared

    async def validate(self, db: AsyncSession, data: dict, instance) -> None:
        code = data.get("code_iso_3166_1")

        if code:
            await self.ensure_unique(db, Country.code_iso_3166_1, code.upper(), "error.code-already-used", "code_iso_3166_1", instance)

    async def list_offered(self, db: AsyncSession) -> list[Country]:
        """What the address form of the site offers, which is every country somebody is allowed to write an address in."""
        return list((await db.execute(select(Country).where(Country.active.is_(True)).order_by(Country.name.asc(), Country.id.asc()))).scalars())

    async def find_by_code(self, db: AsyncSession, code: str) -> Country | None:
        return await db.scalar(select(Country).where(Country.code_iso_3166_1 == code.upper(), Country.active.is_(True)))


country_service = CountryService()
