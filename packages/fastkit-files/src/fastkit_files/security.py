import hashlib
import re
import secrets

from fastkit_core.errors.exceptions import FastKitError
from fastkit_files.errors import FILE_TOO_LARGE, INVALID_MIME

_EXTENSION = re.compile(r"[^a-zA-Z0-9]+")

ALLOWED_IMAGE_MIME = frozenset({"image/jpeg", "image/png", "image/webp", "image/gif"})


def checksum(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def random_object_key(tenant_id: int | None, extension: str) -> str:
    tenant = "global" if tenant_id is None else str(tenant_id)
    token = secrets.token_hex(16)
    clean_extension = _EXTENSION.sub("", extension).lower() or "bin"

    return f"{tenant}/{token[:2]}/{token}.{clean_extension}"


def enforce_size(data: bytes, max_size_bytes: int) -> None:
    if len(data) > max_size_bytes:
        raise FastKitError(FILE_TOO_LARGE, message="file exceeds the maximum allowed size")


def enforce_mime(declared_mime: str, allowed: frozenset[str]) -> None:
    if declared_mime not in allowed:
        raise FastKitError(INVALID_MIME, message=f"mime type '{declared_mime}' is not allowed")
