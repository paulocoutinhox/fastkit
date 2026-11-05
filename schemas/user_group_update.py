from schemas.common import as_optional
from schemas.user_group_create import UserGroupCreate

UserGroupUpdate = as_optional("UserGroupUpdate", UserGroupCreate)
