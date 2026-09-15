from schemas.common import BaseSchema


class UploadResponse(BaseSchema):
    key: str
    url: str
    size: int
