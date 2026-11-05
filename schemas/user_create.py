from typing import Annotated

from pydantic import AfterValidator, EmailStr, Field

from enums.user_gender import UserGender
from enums.user_role import UserRole
from enums.user_status import UserStatus
from helpers.i18n import translate
from schemas.base_schema import BaseSchema
from schemas.common import FREE_TEXT_MAX, Document, JsonMap, MobilePhone, NewPassword, OptionalReference, Timezone, Username


def operated(status: UserStatus) -> UserStatus:
    """An account is erased by replacing the person, which only the erasure does, so a status written by hand never names it."""
    if status == UserStatus.ERASED:
        raise ValueError(translate("validation.invalid-option"))

    return status


OperatedStatus = Annotated[UserStatus, AfterValidator(operated)]


class UserCreate(BaseSchema):
    tenant_id: OptionalReference
    language_id: OptionalReference
    username: Username = None
    email: EmailStr | None = Field(None, max_length=255)
    document: Document = None
    mobile_phone: MobilePhone = None
    password: NewPassword
    role: UserRole = UserRole.NORMAL
    reaches_shared: bool = False
    status: OperatedStatus = UserStatus.ACTIVE
    first_name: str | None = Field(None, max_length=128)
    last_name: str | None = Field(None, max_length=128)
    nickname: str | None = Field(None, max_length=128)
    gender: UserGender = UserGender.NONE
    avatar: str | None = Field(None, max_length=512)
    timezone: Timezone = "UTC"
    notes: str | None = Field(None, max_length=FREE_TEXT_MAX)
    meta: JsonMap = Field(default_factory=dict)
