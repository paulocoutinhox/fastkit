from enums.banner_placement import BannerPlacement
from schemas.base_schema import BaseSchema


class ActiveBannerSchema(BaseSchema):
    """What the app reads, named by the uuid it counts a view and a click by, with the image resolved into an address it can load."""

    uuid: str
    placement: BannerPlacement
    title: str
    image_url: str | None
    url: str | None
    position: int
