from datetime import datetime

from pydantic import EmailStr, Field, computed_field

from enums.user import UserAddressType, UserGender, UserRole, UserStatus
from helpers.text import display_name
from schemas.common import FREE_TEXT_MAX, BaseSchema, Cpf, MobilePhone, OptionalReference, Reference, Text, TimestampSchema, Timezone, Username, as_optional
from schemas.language import LanguageReference
from schemas.tenant import TenantReference


class NamedAccount(BaseSchema):
    """The one name a screen calls an account by, computed the same way wherever an account is answered."""

    @computed_field
    @property
    def display_name(self) -> str:
        return display_name(self)


class UserReference(NamedAccount):
    id: int
    username: str | None
    email: str | None
    nickname: str | None
    first_name: str | None
    last_name: str | None
    mobile_phone: str | None
    cpf: str | None


class AccountSchema(NamedAccount, TimestampSchema):
    """What an account reads about itself: named by its token, and never by the id the admin uses."""

    token: str
    language_id: int | None
    language: LanguageReference | None
    username: str | None
    email: str | None
    cpf: str | None
    mobile_phone: str | None
    status: UserStatus
    first_name: str | None
    last_name: str | None
    nickname: str | None
    gender: UserGender
    avatar_url: str | None
    timezone: str
    last_login_at: datetime | None


class UserSchema(NamedAccount, TimestampSchema):
    id: int
    token: str
    tenant_id: int | None
    tenant: TenantReference | None
    language_id: int | None
    language: LanguageReference | None
    username: str | None
    email: str | None
    cpf: str | None
    mobile_phone: str | None
    role: UserRole
    reaches_shared: bool
    status: UserStatus
    has_password: bool
    first_name: str | None
    last_name: str | None
    nickname: str | None
    gender: UserGender
    avatar: str | None
    timezone: str
    notes: str | None
    last_login_at: datetime | None
    meta: dict


class UserCreate(BaseSchema):
    tenant_id: OptionalReference
    language_id: OptionalReference
    username: Username = None
    email: EmailStr | None = Field(None, max_length=255)
    cpf: Cpf = None
    mobile_phone: MobilePhone = None
    password: str = Field(min_length=8, max_length=128)
    role: UserRole = UserRole.NORMAL
    reaches_shared: bool = False
    status: UserStatus = UserStatus.ACTIVE
    first_name: str | None = Field(None, max_length=128)
    last_name: str | None = Field(None, max_length=128)
    nickname: str | None = Field(None, max_length=128)
    gender: UserGender = UserGender.NONE
    avatar: str | None = Field(None, max_length=512)
    timezone: Timezone = "UTC"
    notes: str | None = Field(None, max_length=FREE_TEXT_MAX)
    meta: dict = Field(default_factory=dict)


UserUpdate = as_optional("UserUpdate", UserCreate)


class UserAddressSchema(TimestampSchema):
    id: int
    user_id: int
    user: UserReference | None
    type: UserAddressType
    line1: str
    street_number: str | None
    complement: str | None
    district: str | None
    city: str
    state: str
    postal_code: str
    country_code: str
    meta: dict


class UserAddressCreate(BaseSchema):
    user_id: Reference
    type: UserAddressType = UserAddressType.MAIN
    line1: Text(255)
    street_number: str | None = Field(None, max_length=32)
    complement: str | None = Field(None, max_length=255)
    district: str | None = Field(None, max_length=128)
    city: Text(128)
    state: Text(128)
    postal_code: Text(32)
    country_code: str = Field(min_length=2, max_length=2)
    meta: dict = Field(default_factory=dict)


UserAddressUpdate = as_optional("UserAddressUpdate", UserAddressCreate)


class AccountAddressSchema(TimestampSchema):
    """The address of whoever is asking, so naming the account on it would say nothing."""

    id: int
    type: UserAddressType
    line1: str
    street_number: str | None
    complement: str | None
    district: str | None
    city: str
    state: str
    postal_code: str
    country_code: str


class AccountAddressRequest(BaseSchema):
    """The account writes its own address, so the owner is the session and never a field of the payload."""

    line1: str = Field(max_length=255)
    street_number: str | None = Field(None, max_length=32)
    complement: str | None = Field(None, max_length=255)
    district: str | None = Field(None, max_length=128)
    city: str = Field(max_length=128)
    state: str = Field(max_length=128)
    postal_code: str = Field(max_length=32)
    country_code: str = Field(min_length=2, max_length=2)


class AccountAddressListResponse(BaseSchema):
    items: list[AccountAddressSchema]
