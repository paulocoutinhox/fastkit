from pydantic import Field

from schemas.base_schema import BaseSchema
from schemas.common import OptionalReference, Text


class ContentCategoryCreate(BaseSchema):
    tenant_id: OptionalReference
    name: Text(255)
    tag: str | None = Field(None, max_length=255)
    active: bool = True
