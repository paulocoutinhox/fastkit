from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from helpers.scope import reaches_tenant
from models.content_group import ContentGroup
from models.user import User
from models.user_group import UserGroup
from models.user_group_member import UserGroupMember
from services.crud import EDITING
from services.crud_service import CrudService
from services.dependent import Dependent


class UserGroupService(CrudService):
    model = UserGroup
    # An editor opens a page to a group without managing the groups, so resolving one is the most the role is given.
    lookup_roles = EDITING
    search_fields = ("code",)
    text_search_fields = ("name",)
    filter_fields = ("tenant_id", "active")
    ordering_fields = ("id", "code", "name", "created_at")
    default_ordering = "name"
    relations = ("tenant",)
    label_fields = ("name", "code")
    dependents = (Dependent(UserGroupMember, "group_id"), Dependent(ContentGroup, "group_id"))

    async def prepare(self, data: dict, instance) -> dict:
        return self.apply_slug(dict(data), instance, "code", ("name",), "group")

    async def validate(self, db: AsyncSession, data: dict, instance) -> None:
        prepared = await self.prepare(data, instance)
        tenant_id = self.declared(prepared, instance, "tenant_id")

        # A rule names a group by its code, and an account reaches the groups of its brand and those of no brand together, so one code names one group across both.
        # A group of no brand is reached by every brand, so its code is free of every group there is.
        scope = None if tenant_id is None else reaches_tenant(UserGroup.tenant_id, tenant_id)

        await self.ensure_unique(db, UserGroup.code, self.declared(prepared, instance, "code"), "error.code-already-used", "code", instance, scope)

    async def codes_of(self, db: AsyncSession, user: User) -> frozenset[str]:
        """The codes of the active groups this account is a member of, which is what an access rule naming a group is answered by."""
        statement = select(UserGroup.code).join(UserGroupMember, UserGroupMember.group_id == UserGroup.id).where(UserGroupMember.user_id == user.id, UserGroup.active.is_(True))

        return frozenset((await db.execute(statement)).scalars())


user_group_service = UserGroupService()
