from schemas.gallery_reference import GalleryReference
from schemas.timestamp_schema import TimestampSchema


class GalleryPhotoSchema(TimestampSchema):
    id: int
    uuid: str
    gallery_id: int
    gallery: GalleryReference | None
    image: str
    caption: str | None
    position: int
