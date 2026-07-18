from fastkit_core.errors.codes import ErrorCode, Severity

INVALID_MIME = ErrorCode(
    "file.invalid_mime",
    400,
    "error.file-invalid-mime",
    Severity.warning,
    should_log=False,
)
FILE_TOO_LARGE = ErrorCode(
    "file.too_large", 400, "error.file-too-large", Severity.warning, should_log=False
)
TOO_MANY_PIXELS = ErrorCode(
    "file.too_many_pixels",
    400,
    "error.file-too-many-pixels",
    Severity.warning,
    should_log=False,
)
NOT_AN_IMAGE = ErrorCode(
    "file.not_an_image",
    400,
    "error.file-not-an-image",
    Severity.warning,
    should_log=False,
)
UPLOAD_SESSION_EXPIRED = ErrorCode(
    "file.upload_session_expired",
    409,
    "error.file-upload-session-expired",
    Severity.warning,
    should_log=False,
)
PROCESSING_FAILED = ErrorCode(
    "file.processing_failed", 500, "error.file-processing-failed", Severity.error
)
