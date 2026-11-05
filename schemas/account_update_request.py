from pydantic import EmailStr, Field

from enums.user_gender import UserGender
from schemas.base_schema import BaseSchema
from schemas.common import Document, MobilePhone, OptionalReference, Timezone, Username


class AccountUpdateRequest(BaseSchema):
    """What an account writes about itself, where a field left out stays as it is and only what the column lets be nothing may be written as nothing."""

    first_name: str | None = Field(None, max_length=128)
    last_name: str | None = Field(None, max_length=128)
    nickname: str | None = Field(None, max_length=128)
    username: Username = None
    email: EmailStr | None = Field(None, max_length=255)
    document: Document = None
    mobile_phone: MobilePhone = None
    gender: UserGender = UserGender.NONE
    language_id: OptionalReference
    timezone: Timezone = "UTC"
