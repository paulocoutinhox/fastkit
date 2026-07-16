from dataclasses import dataclass
from enum import Enum


class Severity(str, Enum):
    debug = "debug"
    info = "info"
    warning = "warning"
    error = "error"
    critical = "critical"


@dataclass(frozen=True)
class ErrorCode:
    code: str
    http_status: int
    translation_key: str
    severity: Severity = Severity.error
    retryable: bool = False
    should_log: bool = True
    user_visible: bool = True


# validation
VALIDATION_FAILED = ErrorCode("validation.failed", 422, "error.validation-failed", Severity.warning, should_log=False)
VALIDATION_REQUIRED = ErrorCode("validation.required", 422, "error.validation-required", Severity.warning, should_log=False)

# authentication and authorization
AUTHENTICATION_REQUIRED = ErrorCode("authentication.required", 401, "error.authentication-required", Severity.warning, should_log=False)
AUTHENTICATION_FAILED = ErrorCode("authentication.failed", 401, "error.authentication-failed", Severity.warning, should_log=False)
AUTHORIZATION_DENIED = ErrorCode("authorization.denied", 403, "error.authorization-denied", Severity.warning, should_log=False)

# tenant
TENANT_REQUIRED = ErrorCode("tenant.required", 400, "error.tenant-required", Severity.warning, should_log=False)
TENANT_CROSS_ACCESS = ErrorCode("tenant.cross_access", 403, "error.tenant-cross-access", Severity.error)

# resource and conflict
RESOURCE_NOT_FOUND = ErrorCode("resource.not_found", 404, "error.not-found", Severity.info, should_log=False)
CONFLICT_UNIQUE = ErrorCode("conflict.unique", 409, "error.conflict-unique", Severity.warning, should_log=False)
CONFLICT_STATE = ErrorCode("conflict.state", 409, "error.conflict-state", Severity.warning, should_log=False)

# infrastructure
RATE_LIMIT_EXCEEDED = ErrorCode("rate_limit.exceeded", 429, "error.rate-limit-exceeded", Severity.warning, retryable=True, should_log=False)
DATABASE_ERROR = ErrorCode("database.error", 500, "error.database", Severity.critical, retryable=True)
CACHE_ERROR = ErrorCode("cache.error", 500, "error.cache", Severity.error, retryable=True, user_visible=False)
STORAGE_ERROR = ErrorCode("storage.error", 502, "error.storage", Severity.error, retryable=True)
PROVIDER_UNAVAILABLE = ErrorCode("provider.unavailable", 503, "error.provider-unavailable", Severity.error, retryable=True)
PROVIDER_TIMEOUT = ErrorCode("provider.timeout", 504, "error.provider-timeout", Severity.error, retryable=True)

# generic internal
INTERNAL_ERROR = ErrorCode("internal.error", 500, "error.internal", Severity.critical, user_visible=False)
