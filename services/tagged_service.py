from sqlalchemy.ext.asyncio import AsyncSession

from helpers.scope import reaches_tenant
from services.localized_service import LocalizedService


class TaggedService(LocalizedService):
    """A resource a page reaches by its tag, answering in the language that page is written in."""

    localized_key = "tag"
    listing_fields: tuple[str, ...] = ("id",)

    def reachable(self, tenant_id: int | None):
        return self.base_statement().where(self.model.active.is_(True), reaches_tenant(self.model.tenant_id, tenant_id))

    async def find_by_tag(self, db: AsyncSession, tag: str, tenant_id: int | None, language: str | None = None):
        """A tenant sees its own version of a tag first and the shared one only when it has none."""
        return await db.scalar(self.by_language(self.reachable(tenant_id).where(self.model.tag == tag), language))

    async def tags_that_answer(self, db: AsyncSession, wanted: tuple[str, ...], tenant_id: int | None, language: str | None = None) -> set[str]:
        """Which of these tags this brand answers, because a link to a page nobody wrote is a dead link on every page that draws it."""
        answered = (await db.execute(self.by_language(self.reachable(tenant_id).where(self.model.tag.in_(wanted)), language))).scalars().unique()

        return {row.tag for row in answered}

    async def list_reachable(self, db: AsyncSession, tenant_id: int | None, language: str | None = None) -> list:
        """One row per tag, in the order a listing draws them."""
        answered = (await db.execute(self.by_language(self.reachable(tenant_id), language))).scalars().unique()

        return self.one_per_key(answered, self.listing_fields)
