from datetime import date

from schemas.language_reference import LanguageReference
from schemas.tenant_reference import TenantReference
from schemas.timestamp_schema import TimestampSchema


class GallerySchema(TimestampSchema):
    id: int
    uuid: str
    tenant_id: int | None
    tenant: TenantReference | None
    language_id: int | None
    language: LanguageReference | None
    title: str
    tag: str
    description: str | None
    published_at: date | None
    position: int
    active: bool
    meta: dict
