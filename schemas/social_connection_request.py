from enums.authentication_surface import AuthenticationSurface
from schemas.base_schema import BaseSchema


class SocialConnectionRequest(BaseSchema):
    surface: AuthenticationSurface = AuthenticationSurface.SITE
