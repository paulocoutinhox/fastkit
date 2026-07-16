from fastkit_core.errors.codes import ErrorCode, Severity

# authentication
INVALID_CREDENTIALS = ErrorCode("authentication.invalid_credentials", 401, "error.invalid-credentials", Severity.warning, should_log=False)
ACCOUNT_INACTIVE = ErrorCode("authentication.account_inactive", 403, "error.account-inactive", Severity.warning, should_log=False)
ACCOUNT_LOCKED = ErrorCode("authentication.account_locked", 403, "error.account-locked", Severity.warning, should_log=False)
AMBIGUOUS_IDENTITY = ErrorCode("authentication.ambiguous_identity", 409, "error.ambiguous-identity", Severity.warning, should_log=False)
SESSION_INVALID = ErrorCode("authentication.session_invalid", 401, "error.session-invalid", Severity.warning, should_log=False)

# rate limit
RATE_LIMITED = ErrorCode("rate_limit.login", 429, "error.rate-limit-login", Severity.warning, retryable=True, should_log=False)

# recaptcha
RECAPTCHA_MISSING = ErrorCode("recaptcha.missing", 400, "error.recaptcha-missing", Severity.warning, should_log=False)
RECAPTCHA_INVALID = ErrorCode("recaptcha.invalid", 400, "error.recaptcha-invalid", Severity.warning, should_log=False)
RECAPTCHA_LOW_SCORE = ErrorCode("recaptcha.low_score", 400, "error.recaptcha-low-score", Severity.warning, should_log=False)
RECAPTCHA_ACTION_MISMATCH = ErrorCode("recaptcha.action_mismatch", 400, "error.recaptcha-action-mismatch", Severity.warning, should_log=False)
RECAPTCHA_HOSTNAME_MISMATCH = ErrorCode("recaptcha.hostname_mismatch", 400, "error.recaptcha-hostname-mismatch", Severity.warning, should_log=False)
RECAPTCHA_PROVIDER_UNAVAILABLE = ErrorCode("recaptcha.provider_unavailable", 503, "error.recaptcha-provider-unavailable", Severity.error)
