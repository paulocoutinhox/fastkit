from datetime import date

from pydantic import Field

from schemas.base_schema import BaseSchema
from schemas.common import FREE_TEXT_MAX, JsonMap, OptionalReference, Position, Text


class GalleryCreate(BaseSchema):
    tenant_id: OptionalReference
    language_id: OptionalReference
    title: Text(255)
    tag: str | None = Field(None, max_length=255)
    description: str | None = Field(None, max_length=FREE_TEXT_MAX)
    published_at: date | None = None
    position: Position
    active: bool = True
    meta: JsonMap = Field(default_factory=dict)
