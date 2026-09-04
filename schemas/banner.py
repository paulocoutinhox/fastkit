from datetime import datetime

from pydantic import Field

from enums.banner import BannerPlacement
from schemas.common import BaseSchema, LinkUrl, OptionalReference, Position, Text, TimestampSchema, as_optional
from schemas.language import LanguageReference
from schemas.tenant import TenantReference


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


class BannerCreate(BaseSchema):
    tenant_id: OptionalReference
    language_id: OptionalReference
    placement: BannerPlacement = BannerPlacement.HOME
    title: Text(255)
    image: str | None = Field(None, max_length=512)
    url: LinkUrl
    position: Position
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    active: bool = True
    meta: dict = Field(default_factory=dict)


BannerUpdate = as_optional("BannerUpdate", BannerCreate)


class ActiveBannerSchema(BaseSchema):
    """What the app reads, named by the uuid it counts a view and a click by, with the image resolved into an address it can load."""

    uuid: str
    placement: BannerPlacement
    title: str
    image_url: str | None
    url: str | None
    position: int


class BannerCountRequest(BaseSchema):
    """Who is being counted, which a browser carries in a cookie and an application carries here."""

    visitor: str | None = Field(None, max_length=512)
