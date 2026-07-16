from dataclasses import dataclass, field

from fastkit_core.errors.codes import ErrorCode, INTERNAL_ERROR


@dataclass
class FieldError:
    field: str
    code: str
    message: str = ""
    path: list[str] = field(default_factory=list)
    params: dict = field(default_factory=dict)


class FastKitError(Exception):
    """Base error carrying a stable code, translation key and HTTP status."""

    def __init__(self, error_code: ErrorCode, message: str | None = None, field_errors: list[FieldError] | None = None, params: dict | None = None):
        self.error_code = error_code
        self.message = message
        self.field_errors = field_errors or []
        self.params = params or {}

        super().__init__(message or error_code.code)


class ValidationError(FastKitError):
    pass


class AuthenticationError(FastKitError):
    pass


class AuthorizationError(FastKitError):
    pass


class TenantError(FastKitError):
    pass


class NotFoundError(FastKitError):
    pass


class ConflictError(FastKitError):
    pass


class RateLimitError(FastKitError):
    pass


class ProviderError(FastKitError):
    pass


class InternalError(FastKitError):
    def __init__(self, message: str | None = None):
        super().__init__(INTERNAL_ERROR, message)
