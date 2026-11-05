from datetime import datetime

from enums.banner_placement import BannerPlacement
from schemas.language_reference import LanguageReference
from schemas.tenant_reference import TenantReference
from schemas.timestamp_schema import TimestampSchema


class BannerSchema(TimestampSchema):
    id: int
    uuid: str
    tenant_id: int | None
    tenant: TenantReference | None
    language_id: int | None
    language: LanguageReference | None
    placement: BannerPlacement
    title: str
    image: str | None
    url: str | None
    position: int
    starts_at: datetime | None
    ends_at: datetime | None
    active: bool
    views: int
    clicks: int
    meta: dict
