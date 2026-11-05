from schemas.common import as_optional
from schemas.user_group_member_create import UserGroupMemberCreate

UserGroupMemberUpdate = as_optional("UserGroupMemberUpdate", UserGroupMemberCreate)
