from pydantic import Field

from schemas.base_schema import BaseSchema
from schemas.common import NewPassword


class PasswordChangeRequest(BaseSchema):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: NewPassword
