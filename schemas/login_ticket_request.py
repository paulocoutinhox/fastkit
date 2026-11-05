from schemas.base_schema import BaseSchema
from schemas.common import SignInToken


class LoginTicketRequest(BaseSchema):
    ticket: SignInToken
