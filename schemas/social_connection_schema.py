from datetime import datetime

from enums.social_provider import SocialProvider
from schemas.base_schema import BaseSchema


class SocialConnectionSchema(BaseSchema):
    provider: SocialProvider
    label: str
    connected: bool
    enabled: bool
    created_at: datetime | None
