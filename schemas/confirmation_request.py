from schemas.base_schema import BaseSchema
from schemas.common import Login


class ConfirmationRequest(BaseSchema):
    login: Login
