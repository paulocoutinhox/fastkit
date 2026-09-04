from fastapi import APIRouter

from helpers import cache
from helpers.auth import CurrentBrand
from helpers.crud import build_router
from helpers.db import DatabaseSession
from helpers.errors import NotFoundError
from helpers.i18n import current_locale
from helpers.storage import storage
from schemas.common import BaseSchema
from schemas.gallery import GalleryCreate, GalleryPhotoCreate, GalleryPhotoSchema, GalleryPhotoUpdate, GallerySchema, GalleryUpdate, PublicGalleryPhotoSchema, PublicGallerySchema
from services.gallery import gallery_photo_service, gallery_service

public_router = APIRouter(prefix="/galleries", tags=["galleries"])


class GalleryListResponse(BaseSchema):
    items: list[PublicGallerySchema]


def present(gallery, photos: list) -> PublicGallerySchema:
    """One gallery as a reader receives it, where the first photo is what stands for the whole set."""
    rendered = [PublicGalleryPhotoSchema(id=photo.id, uuid=photo.uuid, image_url=storage.url(photo.image), caption=photo.caption, position=photo.position) for photo in photos]

    return PublicGallerySchema(id=gallery.id, uuid=gallery.uuid, title=gallery.title, tag=gallery.tag, description=gallery.description, published_at=gallery.published_at, cover_url=rendered[0].image_url if rendered else None, photos=rendered)


@public_router.get("/active", response_model=GalleryListResponse, summary="List the galleries a tenant reaches")
async def list_active(db: DatabaseSession, brand: CurrentBrand):
    language = current_locale.get()

    async def build():
        galleries = await gallery_service.list_reachable(db, brand.id, language)
        photos = await gallery_photo_service.for_galleries(db, [gallery.id for gallery in galleries])

        return [present(gallery, photos.get(gallery.id, [])).model_dump(mode="json") for gallery in galleries]

    entries = await cache.answered(cache.gallery, cache.named(surface="api", tenant=brand.id, language=language), build)

    return GalleryListResponse(items=[PublicGallerySchema(**entry) for entry in entries])


@public_router.get("/by-tag/{tag}", response_model=PublicGallerySchema, summary="Read a gallery by its tag")
async def read_by_tag(db: DatabaseSession, brand: CurrentBrand, tag: str):
    language = current_locale.get()

    async def build():
        gallery = await gallery_service.find_by_tag(db, tag, brand.id, language)

        if gallery is None:
            raise NotFoundError()

        return present(gallery, await gallery_photo_service.list_of(db, gallery.id)).model_dump(mode="json")

    return PublicGallerySchema(**await cache.answered(cache.gallery, cache.named(surface="api", tenant=brand.id, language=language, tag=tag), build))


router = build_router(gallery_service, GallerySchema, GalleryCreate, GalleryUpdate, "/galleries", "galleries")
photo_router = build_router(gallery_photo_service, GalleryPhotoSchema, GalleryPhotoCreate, GalleryPhotoUpdate, "/gallery-photos", "gallery photos")
