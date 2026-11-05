"""The permission error shared by application modules."""

from fastapi import status

from helpers.app_error import AppError


class PermissionError(AppError):
    def __init__(self, code: str = "error.forbidden", **params):
        super().__init__(code, status.HTTP_403_FORBIDDEN, **params)
