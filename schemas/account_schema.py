from datetime import datetime

from enums.user_gender import UserGender
from enums.user_status import UserStatus
from schemas.language_reference import LanguageReference
from schemas.named_account import NamedAccount
from schemas.timestamp_schema import TimestampSchema


class AccountSchema(NamedAccount, TimestampSchema):
    """What an account reads about itself: named by its token, and never by the id the admin uses."""

    token: str
    language_id: int | None
    language: LanguageReference | None
    username: str | None
    email: str | None
    pending_email: str | None
    document: str | None
    mobile_phone: str | None
    status: UserStatus
    first_name: str | None
    last_name: str | None
    nickname: str | None
    gender: UserGender
    avatar_url: str | None
    timezone: str
    last_login_at: datetime | None
    has_password: bool
