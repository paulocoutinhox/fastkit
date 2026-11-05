from pydantic import Field

from enums.banner_placement import BannerPlacement
from schemas.base_schema import BaseSchema
from schemas.common import Instant, JsonMap, LinkUrl, OptionalReference, Position, Text


class BannerCreate(BaseSchema):
    tenant_id: OptionalReference
    language_id: OptionalReference
    placement: BannerPlacement = BannerPlacement.HOME
    title: Text(255)
    image: str | None = Field(None, max_length=512)
    url: LinkUrl
    position: Position
    starts_at: Instant | None = None
    ends_at: Instant | None = None
    active: bool = True
    meta: JsonMap = Field(default_factory=dict)
