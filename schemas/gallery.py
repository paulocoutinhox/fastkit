from datetime import date

from pydantic import Field

from schemas.common import FREE_TEXT_MAX, BaseSchema, OptionalReference, Position, Reference, Text, TimestampSchema, as_optional
from schemas.language import LanguageReference
from schemas.tenant import TenantReference


class GalleryReference(BaseSchema):
    id: int
    uuid: str
    title: str
    tag: str


class GallerySchema(TimestampSchema):
    id: int
    uuid: str
    tenant_id: int | None
    tenant: TenantReference | None
    language_id: int | None
    language: LanguageReference | None
    title: str
    tag: str
    description: str | None
    published_at: date | None
    position: int
    active: bool
    meta: dict


class GalleryCreate(BaseSchema):
    tenant_id: OptionalReference
    language_id: OptionalReference
    title: Text(255)
    tag: str | None = Field(None, max_length=255)
    description: str | None = Field(None, max_length=FREE_TEXT_MAX)
    published_at: date | None = None
    position: Position
    active: bool = True
    meta: dict = Field(default_factory=dict)


GalleryUpdate = as_optional("GalleryUpdate", GalleryCreate)


class GalleryPhotoSchema(TimestampSchema):
    id: int
    uuid: str
    gallery_id: int
    gallery: GalleryReference | None
    image: str
    caption: str | None
    position: int


class GalleryPhotoCreate(BaseSchema):
    gallery_id: Reference
    image: Text(512)
    caption: str | None = Field(None, max_length=255)
    position: Position


GalleryPhotoUpdate = as_optional("GalleryPhotoUpdate", GalleryPhotoCreate)


class PublicGalleryPhotoSchema(BaseSchema):
    id: int
    uuid: str
    image_url: str
    caption: str | None
    position: int


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
