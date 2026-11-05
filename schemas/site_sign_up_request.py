from pydantic import EmailStr, Field

from schemas.base_schema import BaseSchema
from schemas.common import NewPassword


class SiteSignUpRequest(BaseSchema):
    """The site signs a person up by name and address, which is one of the shapes the API accepts and the one a page asks for."""

    first_name: str = Field(min_length=2, max_length=128)
    last_name: str | None = Field(None, max_length=128)
    email: EmailStr = Field(max_length=255)
    password: NewPassword
