from schemas.base_schema import BaseSchema
from schemas.public_gallery_schema import PublicGallerySchema


class GalleryListResponse(BaseSchema):
    items: list[PublicGallerySchema]
