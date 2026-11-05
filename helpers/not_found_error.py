"""The not found error shared by application modules."""

from fastapi import status

from helpers.app_error import AppError


class NotFoundError(AppError):
    def __init__(self, code: str = "error.not-found", **params):
        super().__init__(code, status.HTTP_404_NOT_FOUND, **params)
