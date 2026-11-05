from schemas.timestamp_schema import TimestampSchema
from schemas.user_group_reference import UserGroupReference


class ContentGroupSchema(TimestampSchema):
    id: int
    content_id: int
    group_id: int
    group: UserGroupReference | None
