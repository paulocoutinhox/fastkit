from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from enums.banner import BannerCountKind, BannerPlacement
from enums.upload import UploadPurpose
from helpers.dates import now
from helpers.db import insert_or_read
from helpers.errors import ValidationError
from helpers.scope import reaches_tenant
from models.banner import Banner, BannerImpression
from models.language import Language
from services.crud import EDITING, CrudService


class BannerService(CrudService):
    model = Banner
    roles = EDITING
    search_fields = ("url",)
    text_search_fields = ("title",)
    filter_fields = ("tenant_id", "language_id", "placement", "active")
    ordering_fields = ("id", "title", "placement", "position", "starts_at", "ends_at", "created_at")
    default_ordering = "position"
    relations = ("tenant", "language")
    label_fields = ("title",)
    file_fields = {"image": UploadPurpose.BANNER}

    async def validate(self, db: AsyncSession, data: dict, instance) -> None:
        starts_at = self.declared(data, instance, "starts_at")
        ends_at = self.declared(data, instance, "ends_at")

        if starts_at and ends_at and starts_at > ends_at:
            raise ValidationError("error.availability-window-inverted", "ends_at")

    async def list_active(self, db: AsyncSession, tenant_id: int | None, placement: BannerPlacement | None = None, language: str | None = None) -> list[Banner]:
        """A space asks only for what belongs to it, and asking for nothing answers every space."""
        moment = now()
        statement = self.base_statement().where(Banner.active.is_(True), reaches_tenant(Banner.tenant_id, tenant_id), or_(Banner.starts_at.is_(None), Banner.starts_at <= moment), or_(Banner.ends_at.is_(None), Banner.ends_at >= moment))

        if placement is not None:
            statement = statement.where(Banner.placement == placement)

        # A banner naming no language is the banner of every reader, exactly as a row naming no tenant is of every tenant.
        if language is not None:
            statement = statement.outerjoin(Language, Language.id == Banner.language_id).where(or_(Banner.language_id.is_(None), Language.code_iso_639_1 == language))

        result = await db.execute(statement.order_by(Banner.position.asc(), Banner.id.asc()))

        return list(result.scalars())

    async def find_by_uuid(self, db: AsyncSession, uuid: str, tenant_id: int | None) -> Banner | None:
        """A banner is named outside this application by its uuid, because the id says how many of them exist."""
        return await db.scalar(select(Banner).where(Banner.uuid == uuid, reaches_tenant(Banner.tenant_id, tenant_id)))

    async def count(self, db: AsyncSession, banner: Banner, kind: BannerCountKind, visitor: str) -> bool:
        """One visitor counts once a day for one banner, and the total only moves for whoever wrote that row."""
        today = now().date()
        read = select(BannerImpression).where(BannerImpression.banner_id == banner.id, BannerImpression.kind == kind, BannerImpression.visitor == visitor, BannerImpression.day == today)
        impression = BannerImpression(banner_id=banner.id, kind=kind, visitor=visitor, day=today)
        settled = await insert_or_read(db, impression, read)

        # Whoever lost the race is handed the row the winner wrote, and adding to the total there would count the same visit twice.
        if settled is not impression:
            return False

        column = Banner.views if kind is BannerCountKind.VIEW else Banner.clicks

        # The total is raised by the database, because reading it and writing it back loses every count that arrives at the same moment.
        await db.execute(update(Banner).where(Banner.id == banner.id).values({column: column + 1}))

        return True


banner_service = BannerService()
