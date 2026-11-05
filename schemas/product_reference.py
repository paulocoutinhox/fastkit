from schemas.base_schema import BaseSchema


class ProductReference(BaseSchema):
    id: int
    uuid: str
    name: str
    slug: str
