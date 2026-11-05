from schemas.base_schema import BaseSchema
from schemas.common import Login


class PasswordResetRequest(BaseSchema):
    login: Login
