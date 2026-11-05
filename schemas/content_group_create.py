from schemas.base_schema import BaseSchema
from schemas.common import Reference


class ContentGroupCreate(BaseSchema):
    content_id: Reference
    group_id: Reference
