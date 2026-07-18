from fastkit_core.errors.codes import ErrorCode, Severity

# authentication
INVALID_CREDENTIALS = ErrorCode("authentication.invalid_credentials", 401, "error.invalid-credentials", Severity.warning, should_log=False)
ACCOUNT_INACTIVE = ErrorCode("authentication.account_inactive", 403, "error.account-inactive", Severity.warning, should_log=False)
ACCOUNT_LOCKED = ErrorCode("authentication.account_locked", 403, "error.account-locked", Severity.warning, should_log=False)
AMBIGUOUS_IDENTITY = ErrorCode("authentication.ambiguous_identity", 409, "error.ambiguous-identity", Severity.warning, should_log=False)
SESSION_INVALID = ErrorCode("authentication.session_invalid", 401, "error.session-invalid", Severity.warning, should_log=False)

# rate limit
RATE_LIMITED = ErrorCode("rate_limit.login", 429, "error.rate-limit-login", Severity.warning, retryable=True, should_log=False)

# captcha
CAPTCHA_REQUIRED = ErrorCode("captcha.required", 400, "error.captcha-required", Severity.warning, should_log=False)
CAPTCHA_INVALID = ErrorCode("captcha.invalid", 400, "error.captcha-invalid", Severity.warning, should_log=False)
CAPTCHA_EXPIRED = ErrorCode("captcha.expired", 400, "error.captcha-expired", Severity.warning, should_log=False)
CAPTCHA_PROVIDER_UNAVAILABLE = ErrorCode("captcha.provider_unavailable", 503, "error.captcha-provider-unavailable", Severity.error)
