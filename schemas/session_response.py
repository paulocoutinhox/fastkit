from schemas.account_schema import AccountSchema
from schemas.base_schema import BaseSchema


class SessionResponse(BaseSchema):
    """What an answer that may start a session carries, where a token of nothing says no session starts here: a sign up whose address has to answer first, or an address change a letter proved."""

    token: str | None
    user: AccountSchema
