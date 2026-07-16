from fastkit_core.errors.codes import ErrorCode, Severity

INVALID_MIME = ErrorCode("asset.invalid_mime", 400, "error.asset-invalid-mime", Severity.warning, should_log=False)
FILE_TOO_LARGE = ErrorCode("asset.too_large", 400, "error.asset-too-large", Severity.warning, should_log=False)
TOO_MANY_PIXELS = ErrorCode("asset.too_many_pixels", 400, "error.asset-too-many-pixels", Severity.warning, should_log=False)
NOT_AN_IMAGE = ErrorCode("asset.not_an_image", 400, "error.asset-not-an-image", Severity.warning, should_log=False)
UPLOAD_SESSION_EXPIRED = ErrorCode("asset.upload_session_expired", 409, "error.asset-upload-session-expired", Severity.warning, should_log=False)
PROCESSING_FAILED = ErrorCode("asset.processing_failed", 500, "error.asset-processing-failed", Severity.error)
