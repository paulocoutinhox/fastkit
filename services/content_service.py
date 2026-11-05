from sqlalchemy.ext.asyncio import AsyncSession

from models.content import Content
from models.content_category import ContentCategory
from services.crud import EDITING
from services.tagged_service import TaggedService


class ContentService(TaggedService):
    model = Content
    shared = True
    markup_fields = ("content",)
    roles = EDITING
    search_fields = ("tag",)
    text_search_fields = ("title",)
    filter_fields = ("tenant_id", "category_id", "language_id", "active")
    ordering_fields = ("id", "title", "tag", "published_at", "created_at")
    default_ordering = "-id"
    relations = ("tenant", "category", "language")
    label_fields = ("title",)

    async def prepare(self, data: dict, instance) -> dict:
        return self.apply_slug(dict(data), instance, "tag", ("title",), "content")

    async def validate(self, db: AsyncSession, data: dict, instance) -> None:
        await self.ensure_reaches(db, ContentCategory, self.declared(data, instance, "category_id"), self.declared(data, instance, "tenant_id"), "category_id")


content_service = ContentService()
