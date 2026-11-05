from schemas.base_schema import BaseSchema


class GalleryReference(BaseSchema):
    id: int
    uuid: str
    title: str
    tag: str
