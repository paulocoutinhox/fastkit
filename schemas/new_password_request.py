from schemas.base_schema import BaseSchema
from schemas.common import NewPassword


class NewPasswordRequest(BaseSchema):
    """A password being set, which the site asks for alone because the token that allows it is in the address."""

    new_password: NewPassword
