"""The validation error shared by application modules."""

from fastapi import status

from helpers.app_error import AppError


class ValidationError(AppError):
    def __init__(self, code: str, field: str | None = None, **params):
        super().__init__(code, status.HTTP_422_UNPROCESSABLE_CONTENT, field, **params)
