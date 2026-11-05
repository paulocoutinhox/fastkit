from datetime import datetime

from enums.user_gender import UserGender
from enums.user_role import UserRole
from enums.user_status import UserStatus
from schemas.language_reference import LanguageReference
from schemas.named_account import NamedAccount
from schemas.tenant_reference import TenantReference
from schemas.timestamp_schema import TimestampSchema


class UserSchema(NamedAccount, TimestampSchema):
    id: int
    token: str
    tenant_id: int | None
    tenant: TenantReference | None
    language_id: int | None
    language: LanguageReference | None
    username: str | None
    email: str | None
    document: str | None
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
