from enums.social_provider import SocialProvider
from schemas.base_schema import BaseSchema


class SocialMethodSchema(BaseSchema):
    provider: SocialProvider
    label: str
