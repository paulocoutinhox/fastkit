from schemas.base_schema import BaseSchema


class AppEventBatchResponse(BaseSchema):
    accepted: int
    duplicated: int
