from schemas.base_schema import BaseSchema


class SocialAuthorizationResponse(BaseSchema):
    authorization_url: str
