from fastkit_core.errors.codes import ErrorCode, Severity

OBJECT_NOT_FOUND = ErrorCode(
    "storage.object_not_found",
    404,
    "error.storage-object-not-found",
    Severity.warning,
    should_log=False,
)
UNSAFE_PATH = ErrorCode(
    "storage.unsafe_path", 400, "error.storage-unsafe-path", Severity.error
)
