from fastkit_core.errors.codes import ErrorCode
from fastkit_core.errors.exceptions.field_error import FieldError


class FastKitError(Exception):
    """Base error carrying a stable code, translation key and HTTP status."""

    def __init__(self, error_code: ErrorCode, message: str | None = None, field_errors: list[FieldError] | None = None, params: dict | None = None):
        self.error_code = error_code
        self.message = message
        self.field_errors = field_errors or []
        self.params = params or {}

        super().__init__(message or error_code.code)
