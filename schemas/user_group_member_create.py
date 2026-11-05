from schemas.base_schema import BaseSchema
from schemas.common import Reference


class UserGroupMemberCreate(BaseSchema):
    group_id: Reference
    user_id: Reference
