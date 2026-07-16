from pathlib import PurePosixPath

from fastkit_core.errors.exceptions import FastKitError
from fastkit_storage.errors import UNSAFE_PATH


def safe_key(key: str) -> str:
    """Reject absolute paths and traversal so an object key can never escape its root."""

    normalized = key.strip().lstrip("/")

    if not normalized:
        raise FastKitError(UNSAFE_PATH, message="empty object key")

    parts = PurePosixPath(normalized).parts

    if any(part == ".." for part in parts):
        raise FastKitError(UNSAFE_PATH, message="object key must not contain '..'")

    return normalized
