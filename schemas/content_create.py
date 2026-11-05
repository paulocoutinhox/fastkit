from datetime import date

from pydantic import Field

from enums.content_audience import ContentAudience
from schemas.base_schema import BaseSchema
from schemas.common import FREE_TEXT_MAX, JsonMap, OptionalReference, Text


class ContentCreate(BaseSchema):
    tenant_id: OptionalReference
    category_id: OptionalReference
    language_id: OptionalReference
    title: Text(255)
    tag: str | None = Field(None, max_length=255)
    content: str | None = Field(None, max_length=FREE_TEXT_MAX)
    published_at: date | None = None
    active: bool = True
    audience: ContentAudience = ContentAudience.EVERYONE
    meta: JsonMap = Field(default_factory=dict)
