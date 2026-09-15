from sqlalchemy.ext.asyncio import AsyncSession

from models.content import Content, ContentCategory
from services.crud import EDITING, CrudService, TaggedService


class ContentCategoryService(CrudService):
    model = ContentCategory
    roles = EDITING
    search_fields = ("tag",)
    text_search_fields = ("name",)
    filter_fields = ("tenant_id", "active")
    ordering_fields = ("id", "name", "tag", "created_at")
    default_ordering = "name"
    relations = ("tenant",)
    label_fields = ("name",)

    async def prepare(self, data: dict, instance) -> dict:
        return self.apply_slug(dict(data), instance, "tag", ("name",), "category")

    async def validate(self, db: AsyncSession, data: dict, instance) -> None:
        prepared = await self.prepare(data, instance)

        await self.ensure_unique(db, ContentCategory.tag, prepared.get("tag"), "error.tag-already-used", "tag", instance)


class ContentService(TaggedService):
    model = Content
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


content_category_service = ContentCategoryService()
content_service = ContentService()
