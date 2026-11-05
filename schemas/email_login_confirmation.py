from enums.authentication_surface import AuthenticationSurface
from schemas.base_schema import BaseSchema
from schemas.common import SignInCode, SignInToken


class EmailLoginConfirmation(BaseSchema):
    challenge: SignInToken
    code: SignInCode
    surface: AuthenticationSurface = AuthenticationSurface.SITE
