from pydantic import Field

from schemas.base_schema import BaseSchema
from schemas.common import SignInToken


class SocialCallbackRequest(BaseSchema):
    state: SignInToken
    code: str | None = Field(default=None, max_length=4096)
    error: str | None = Field(default=None, max_length=128)
