from pydantic import Field

from schemas.new_password_request import NewPasswordRequest


class PasswordResetConfirmRequest(NewPasswordRequest):
    token: str = Field(min_length=8, max_length=128)
