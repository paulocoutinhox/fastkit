from pydantic import EmailStr, Field

from enums.user import UserGender
from schemas.common import BaseSchema, CaptchaAnswer, CaptchaToken, Document, Login, MobilePhone, NewPassword, OptionalReference, Timezone, Username
from schemas.user import AccountSchema


class Challenged(BaseSchema):
    """A form anybody may send carries the challenge the environment declared, the same wherever it is drawn."""

    captcha_answer: CaptchaAnswer = None
    captcha_token: CaptchaToken = None


class SignInRequest(BaseSchema):
    login: Login
    password: str = Field(min_length=1, max_length=128)


class AdminSignInRequest(SignInRequest, Challenged):
    """The admin is a form somebody types into, so it carries the challenge the environment declared."""


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


class TokenResponse(BaseSchema):
    token: str
    user: AccountSchema


class SessionResponse(BaseSchema):
    """What an answer that may start a session carries, where a token of nothing says no session starts here: a sign up whose address has to answer first, or an address change a letter proved."""

    token: str | None
    user: AccountSchema


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


class PasswordChangeRequest(BaseSchema):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: NewPassword


class PasswordResetRequest(BaseSchema):
    login: Login


class NewPasswordRequest(BaseSchema):
    """A password being set, which the site asks for alone because the token that allows it is in the address."""

    new_password: NewPassword


class PasswordResetConfirmRequest(NewPasswordRequest):
    token: str = Field(min_length=8, max_length=128)


class ConfirmationRequest(BaseSchema):
    login: Login


class SiteSignUpRequest(BaseSchema):
    """The site signs a person up by name and address, which is one of the shapes the API accepts and the one a page asks for."""

    first_name: str = Field(min_length=2, max_length=128)
    last_name: str | None = Field(None, max_length=128)
    email: EmailStr = Field(max_length=255)
    password: NewPassword
