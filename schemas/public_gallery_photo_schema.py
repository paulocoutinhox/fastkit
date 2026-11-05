from schemas.base_schema import BaseSchema


class PublicGalleryPhotoSchema(BaseSchema):
    id: int
    uuid: str
    image_url: str
    caption: str | None
    position: int
