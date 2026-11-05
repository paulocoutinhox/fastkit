from pydantic import EmailStr, Field

from enums.user_gender import UserGender
from schemas.base_schema import BaseSchema
from schemas.common import Document, MobilePhone, NewPassword, OptionalReference, Timezone, Username


class SignUpRequest(BaseSchema):
    """An account is created with at least one of the four it is later signed in by."""

    password: NewPassword
    username: Username = None
    email: EmailStr | None = Field(None, max_length=255)
    document: Document = None
    mobile_phone: MobilePhone = None
    first_name: str | None = Field(None, max_length=128)
    last_name: str | None = Field(None, max_length=128)
    nickname: str | None = Field(None, max_length=128)
    gender: UserGender = UserGender.NONE
    language_id: OptionalReference
    timezone: Timezone = "UTC"
