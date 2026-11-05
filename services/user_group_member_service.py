from sqlalchemy.ext.asyncio import AsyncSession

from helpers.validation_error import ValidationError
from models.user import User
from models.user_group import UserGroup
from models.user_group_member import UserGroupMember
from services.crud_service import CrudService
from services.reach import Reach


class UserGroupMemberService(CrudService):
    model = UserGroupMember
    reaches_through = Reach(UserGroupMember.group_id, UserGroup)
    filter_fields = ("group_id", "user_id")
    ordering_fields = ("id", "created_at")
    default_ordering = "-id"
    relations = ("group", "user")
    label_fields = ("id",)

    async def validate(self, db: AsyncSession, data: dict, instance) -> None:
        """A group of one brand holds the accounts of that brand, and a group of no brand holds any account of the instance."""
        group = await db.get(UserGroup, self.declared(data, instance, "group_id"))
        member = await db.get(User, self.declared(data, instance, "user_id"))

        if group.tenant_id is not None and member.tenant_id != group.tenant_id:
            raise ValidationError("error.member-of-another-brand", "user_id")


user_group_member_service = UserGroupMemberService()
