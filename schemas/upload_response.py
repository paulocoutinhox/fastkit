from schemas.base_schema import BaseSchema


class UploadResponse(BaseSchema):
    key: str
    url: str
    size: int
