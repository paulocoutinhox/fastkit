from sqlalchemy.ext.asyncio import AsyncSession

from models.content import Content
from models.content_group import ContentGroup
from models.user_group import UserGroup
from services.crud import EDITING
from services.crud_service import CrudService
from services.reach import Reach


class ContentGroupService(CrudService):
    model = ContentGroup
    shared = True
    reaches_through = Reach(ContentGroup.content_id, Content)
    roles = EDITING
    filter_fields = ("content_id", "group_id")
    ordering_fields = ("id", "created_at")
    default_ordering = "-id"
    relations = ("group",)
    label_fields = ("id",)

    async def validate(self, db: AsyncSession, data: dict, instance) -> None:
        """A page of one brand is opened to the groups that brand reaches, and a shared page only to the groups every brand shares."""
        content = await db.get(Content, self.declared(data, instance, "content_id"))

        await self.ensure_reaches(db, UserGroup, self.declared(data, instance, "group_id"), content.tenant_id, "group_id")


content_group_service = ContentGroupService()
