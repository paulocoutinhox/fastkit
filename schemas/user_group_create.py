from pydantic import Field

from schemas.base_schema import BaseSchema
from schemas.common import OptionalReference, Text


class UserGroupCreate(BaseSchema):
    tenant_id: OptionalReference
    code: str | None = Field(None, max_length=64)
    name: Text(255)
    active: bool = True
