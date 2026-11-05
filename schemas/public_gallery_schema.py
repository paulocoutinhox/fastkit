from datetime import date

from schemas.base_schema import BaseSchema
from schemas.public_gallery_photo_schema import PublicGalleryPhotoSchema


class PublicGallerySchema(BaseSchema):
    """What a visitor reads, with every image resolved into an address instead of a storage key."""

    id: int
    uuid: str
    title: str
    tag: str
    description: str | None
    published_at: date | None
    cover_url: str | None
    photos: list[PublicGalleryPhotoSchema]
