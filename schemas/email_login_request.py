from enums.authentication_surface import AuthenticationSurface
from schemas.challenged import Challenged
from schemas.common import EmailAddress


class EmailLoginRequest(Challenged):
    email: EmailAddress
    surface: AuthenticationSurface = AuthenticationSurface.SITE
