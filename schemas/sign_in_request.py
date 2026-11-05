from pydantic import Field

from schemas.base_schema import BaseSchema
from schemas.common import Login


class SignInRequest(BaseSchema):
    login: Login
    password: str = Field(min_length=1, max_length=128)
