from schemas.base_schema import BaseSchema


class ContentCategoryReference(BaseSchema):
    id: int
    uuid: str
    name: str
    tag: str
