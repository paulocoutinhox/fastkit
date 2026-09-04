from datetime import date

from pydantic import Field

from schemas.common import FREE_TEXT_MAX, BaseSchema, OptionalReference, Text, TimestampSchema, as_optional
from schemas.language import LanguageReference
from schemas.tenant import TenantReference


class ContentCategoryReference(BaseSchema):
    id: int
    uuid: str
    name: str
    tag: str


class ContentCategorySchema(TimestampSchema):
    id: int
    uuid: str
    tenant_id: int | None
    tenant: TenantReference | None
    name: str
    tag: str
    active: bool


class ContentCategoryCreate(BaseSchema):
    tenant_id: OptionalReference
    name: Text(255)
    tag: str | None = Field(None, max_length=255)
    active: bool = True


ContentCategoryUpdate = as_optional("ContentCategoryUpdate", ContentCategoryCreate)


class ContentSchema(TimestampSchema):
    id: int
    uuid: str
    tenant_id: int | None
    tenant: TenantReference | None
    category_id: int | None
    category: ContentCategoryReference | None
    language_id: int | None
    language: LanguageReference | None
    title: str
    tag: str
    content: str | None
    published_at: date | None
    active: bool
    meta: dict


class ContentCreate(BaseSchema):
    tenant_id: OptionalReference
    category_id: OptionalReference
    language_id: OptionalReference
    title: Text(255)
    tag: str | None = Field(None, max_length=255)
    content: str | None = Field(None, max_length=FREE_TEXT_MAX)
    published_at: date | None = None
    active: bool = True
    meta: dict = Field(default_factory=dict)


ContentUpdate = as_optional("ContentUpdate", ContentCreate)
