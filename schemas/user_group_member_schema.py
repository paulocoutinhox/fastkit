from schemas.timestamp_schema import TimestampSchema
from schemas.user_group_reference import UserGroupReference
from schemas.user_reference import UserReference


class UserGroupMemberSchema(TimestampSchema):
    id: int
    group_id: int
    group: UserGroupReference | None
    user_id: int
    user: UserReference | None
