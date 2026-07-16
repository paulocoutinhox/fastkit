from fastkit_core.errors.codes import VALIDATION_FAILED
from fastkit_core.errors.exceptions import FieldError, ValidationError

DEFAULT_MAX_UPLOAD_BYTES = 25 * 1024 * 1024


async def read_upload(file, max_bytes: int = DEFAULT_MAX_UPLOAD_BYTES) -> bytes:
    """Read an upload into memory with a hard byte cap, rejecting anything larger."""

    data = await file.read(max_bytes + 1)

    if len(data) > max_bytes:
        raise ValidationError(VALIDATION_FAILED, field_errors=[FieldError("file", "validation.file-too-large", params={"max_bytes": max_bytes})])

    return data
