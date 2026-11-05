from datetime import datetime

from schemas.base_schema import BaseSchema


class EmailLoginResponse(BaseSchema):
    challenge: str
    expires_at: datetime
    resend_at: datetime
