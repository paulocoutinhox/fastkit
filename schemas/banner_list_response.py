from schemas.active_banner_schema import ActiveBannerSchema
from schemas.base_schema import BaseSchema


class BannerListResponse(BaseSchema):
    items: list[ActiveBannerSchema]
