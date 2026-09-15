from pydantic import EmailStr, Field

from enums.user import UserGender
from schemas.common import BaseSchema, Document, MobilePhone, OptionalReference, Timezone, Username
from schemas.user import AccountSchema


class SignInRequest(BaseSchema):
    login: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=128)


class AdminSignInRequest(SignInRequest):
    """The admin is a form somebody types into, so it carries the challenge the environment declared."""

    captcha_answer: str = Field("", max_length=512)
    captcha_token: str = Field("", max_length=1024)


class SignUpRequest(BaseSchema):
    """An account is created with at least one of the four it is later signed in by."""

    password: str = Field(min_length=8, max_length=128)
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


class TokenResponse(BaseSchema):
    token: str
    user: AccountSchema


class SignUpResponse(BaseSchema):
    """What signing up answers, where a token of nothing is the account saying its address has to answer first."""

    token: str | None
    user: AccountSchema


class AccountUpdateRequest(BaseSchema):
    """What an account writes about itself, where a field left out stays as it is and only what the column lets be nothing may be written as nothing."""

    email: EmailStr | None = Field(None, max_length=255)
    mobile_phone: MobilePhone = None
    first_name: str | None = Field(None, max_length=128)
    last_name: str | None = Field(None, max_length=128)
    nickname: str | None = Field(None, max_length=128)
    gender: UserGender = UserGender.NONE
    language_id: OptionalReference
    timezone: Timezone = "UTC"


class PasswordChangeRequest(BaseSchema):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class PasswordResetRequest(BaseSchema):
    login: str = Field(min_length=3, max_length=255)


class PasswordResetConfirmRequest(BaseSchema):
    token: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class ConfirmationRequest(BaseSchema):
    login: str = Field(min_length=3, max_length=255)
