from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from enums.upload import UploadPurpose
from models.gallery import Gallery, GalleryPhoto
from services.crud import EDITING, CrudService, Dependent, Reach, TaggedService


class GalleryService(TaggedService):
    model = Gallery
    roles = EDITING
    search_fields = ("tag",)
    text_search_fields = ("title",)
    filter_fields = ("tenant_id", "language_id", "active")
    ordering_fields = ("id", "title", "tag", "position", "published_at", "created_at")
    default_ordering = "position"
    relations = ("tenant", "language")
    label_fields = ("title",)
    position_field = "position"
    listing_fields = ("position", "id")
    dependents = (Dependent(GalleryPhoto, "gallery_id"),)

    async def prepare(self, data: dict, instance) -> dict:
        return self.apply_slug(dict(data), instance, "tag", ("title",), "gallery")


class GalleryPhotoService(CrudService):
    model = GalleryPhoto
    reaches_through = Reach(GalleryPhoto.gallery_id, Gallery)
    roles = EDITING
    search_fields = ("caption",)
    filter_fields = ("gallery_id",)
    ordering_fields = ("id", "position", "created_at")
    default_ordering = "position"
    relations = ("gallery",)
    label_fields = ("caption",)
    file_fields = {"image": UploadPurpose.GALLERY_PHOTO}
    position_field = "position"

    async def list_of(self, db: AsyncSession, gallery_id: int) -> list[GalleryPhoto]:
        result = await db.execute(select(GalleryPhoto).where(GalleryPhoto.gallery_id == gallery_id).order_by(GalleryPhoto.position.asc(), GalleryPhoto.id.asc()))

        return list(result.scalars())

    async def for_galleries(self, db: AsyncSession, gallery_ids: list[int]) -> dict[int, list[GalleryPhoto]]:
        """The photos of each of these galleries, answered in one go because a listing is otherwise a query per gallery."""
        if not gallery_ids:
            return {}

        rows = (await db.execute(select(GalleryPhoto).where(GalleryPhoto.gallery_id.in_(gallery_ids)).order_by(GalleryPhoto.gallery_id.asc(), GalleryPhoto.position.asc(), GalleryPhoto.id.asc()))).scalars()
        grouped: dict[int, list[GalleryPhoto]] = {}

        for photo in rows:
            grouped.setdefault(photo.gallery_id, []).append(photo)

        return grouped

    async def covers_for(self, db: AsyncSession, gallery_ids: list[int]) -> dict[int, str]:
        """The image standing for each of these galleries, answered in one go because a card per gallery is otherwise a query per gallery."""
        if not gallery_ids:
            return {}

        # The first position stands for the whole set, so nothing carries a second way of saying which one that is.
        rows = await db.execute(select(GalleryPhoto.gallery_id, GalleryPhoto.image).where(GalleryPhoto.gallery_id.in_(gallery_ids)).order_by(GalleryPhoto.gallery_id.asc(), GalleryPhoto.position.asc(), GalleryPhoto.id.asc()))
        covers: dict[int, str] = {}

        for gallery_id, image in rows:
            covers.setdefault(gallery_id, image)

        return covers


gallery_service = GalleryService()
gallery_photo_service = GalleryPhotoService()
