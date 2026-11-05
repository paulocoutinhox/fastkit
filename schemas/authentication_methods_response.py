from schemas.base_schema import BaseSchema
from schemas.social_method_schema import SocialMethodSchema


class AuthenticationMethodsResponse(BaseSchema):
    email_code: bool
    social: list[SocialMethodSchema]
