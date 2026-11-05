from pydantic import Field

from schemas.base_schema import BaseSchema
from schemas.common import Position, Reference, Text


class GalleryPhotoCreate(BaseSchema):
    gallery_id: Reference
    image: Text(512)
    caption: str | None = Field(None, max_length=255)
    position: Position
