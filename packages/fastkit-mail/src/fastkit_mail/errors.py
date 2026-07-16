from fastkit_core.errors.codes import ErrorCode, Severity

TEMPLATE_NOT_FOUND = ErrorCode("email.template_not_found", 500, "error.email-template-not-found", Severity.error)
SEND_FAILED = ErrorCode("email.send_failed", 502, "error.email-send-failed", Severity.error, retryable=True)
