"""The authentication error shared by application modules."""

from fastapi import status

from helpers.app_error import AppError


class AuthenticationError(AppError):
    def __init__(self, code: str = "error.unauthorized", **params):
        super().__init__(code, status.HTTP_401_UNAUTHORIZED, **params)
