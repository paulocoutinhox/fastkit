"""A domain failure carrying a translation key, so the message is rendered in the caller language."""

from fastapi import status

from helpers.i18n import translate


class AppError(Exception):
    def __init__(self, code: str, status_code: int = status.HTTP_400_BAD_REQUEST, field: str | None = None, **params):
        super().__init__(code)

        self.code = code
        self.status_code = status_code
        self.field = field
        self.params = params

    @property
    def message(self) -> str:
        return translate(self.code, **self.params)
