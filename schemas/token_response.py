from schemas.account_schema import AccountSchema
from schemas.base_schema import BaseSchema


class TokenResponse(BaseSchema):
    token: str
    user: AccountSchema
