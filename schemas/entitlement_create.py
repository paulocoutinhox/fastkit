from pydantic import Field

from schemas.base_schema import BaseSchema
from schemas.common import FREE_TEXT_MAX, JsonMap, OptionalReference, Text


class EntitlementCreate(BaseSchema):
    tenant_id: OptionalReference
    code: Text(64)
    name: Text(255)
    description: str | None = Field(None, max_length=FREE_TEXT_MAX)
    active: bool = True
    meta: JsonMap = Field(default_factory=dict)
