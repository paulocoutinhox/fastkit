from models.gallery import Gallery
from models.gallery_photo import GalleryPhoto
from services.crud import EDITING
from services.dependent import Dependent
from services.tagged_service import TaggedService


class GalleryService(TaggedService):
    model = Gallery
    shared = True
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


gallery_service = GalleryService()
