from sqlalchemy.ext.asyncio import AsyncSession

from helpers.scope import belongs_to_tenant
from models.content_category import ContentCategory
from services.crud import EDITING
from services.crud_service import CrudService


class ContentCategoryService(CrudService):
    model = ContentCategory
    shared = True
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

        # The tag is unique inside a brand, which is what the index says, so another brand holding it takes nothing from this one.
        await self.ensure_unique(db, ContentCategory.tag, prepared.get("tag"), "error.tag-already-used", "tag", instance, belongs_to_tenant(ContentCategory.tenant_id, self.declared(prepared, instance, "tenant_id")))


content_category_service = ContentCategoryService()
