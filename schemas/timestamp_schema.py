from datetime import datetime

from schemas.base_schema import BaseSchema


class TimestampSchema(BaseSchema):
    created_at: datetime
    updated_at: datetime
