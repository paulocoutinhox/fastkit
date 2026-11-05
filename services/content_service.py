from collections.abc import Callable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from enums.content_audience import ContentAudience
from models.content import Content
from models.content_category import ContentCategory
from models.content_group import ContentGroup
from models.user import User
from models.user_group import UserGroup
from services.access_rule import AccessRule
from services.crud import EDITING
from services.dependent import Dependent
from services.everyone import Everyone
from services.in_group import InGroup
from services.signed_in import SignedIn
from services.tagged_service import TaggedService

# Who each audience lets in, where the members of a page are the active groups it names and a page naming none is drawn for nobody.
AUDIENCES: dict[ContentAudience, Callable[[list[str]], AccessRule]] = {ContentAudience.EVERYONE: lambda groups: Everyone(), ContentAudience.SIGNED_IN: lambda groups: SignedIn(), ContentAudience.MEMBERS: lambda groups: InGroup(*groups)}


class ContentService(TaggedService):
    model = Content
    shared = True
    markup_fields = ("content",)
    roles = EDITING
    search_fields = ("tag",)
    text_search_fields = ("title",)
    filter_fields = ("tenant_id", "category_id", "language_id", "active", "audience")
    ordering_fields = ("id", "title", "tag", "published_at", "created_at")
    default_ordering = "-id"
    relations = ("tenant", "category", "language")
    label_fields = ("title",)
    dependents = (Dependent(ContentGroup, "content_id"),)

    async def prepare(self, data: dict, instance) -> dict:
        return self.apply_slug(dict(data), instance, "tag", ("title",), "content")

    async def validate(self, db: AsyncSession, data: dict, instance) -> None:
        await self.ensure_reaches(db, ContentCategory, self.declared(data, instance, "category_id"), self.declared(data, instance, "tenant_id"), "category_id")

    async def groups_of(self, db: AsyncSession, content: Content) -> list[str]:
        """The codes of the active groups a page is opened to, kept beside the page so reading it again never asks for them."""
        statement = select(UserGroup.code).join(ContentGroup, ContentGroup.group_id == UserGroup.id).where(ContentGroup.content_id == content.id, UserGroup.active.is_(True)).order_by(UserGroup.code.asc())

        return list((await db.execute(statement)).scalars())

    async def list_public(self, db: AsyncSession, tenant_id: int | None) -> list:
        """The pages anybody reads, which is every page a crawler is offered."""
        return [content for content in await self.list_reachable(db, tenant_id) if content.audience == ContentAudience.EVERYONE]

    def opens_to_nobody(self, audience: ContentAudience, groups: list[str]) -> bool:
        """Whether no account could ever read a page, which a page for members naming no active group is, so signing in would lead nowhere."""
        return audience == ContentAudience.MEMBERS and not groups

    async def admits(self, db: AsyncSession, audience: ContentAudience, groups: list[str], user: User | None) -> bool:
        """Whether this reader may read a page drawn for that audience and those groups."""
        return await AUDIENCES[audience](groups).admits(db, user)


content_service = ContentService()
