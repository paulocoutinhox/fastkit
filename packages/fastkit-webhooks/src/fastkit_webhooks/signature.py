import hashlib
import hmac


def compute_signature(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def verify_signature(secret: str, body: bytes, provided: str | None) -> bool:
    if not provided:
        return False

    return hmac.compare_digest(compute_signature(secret, body), provided)
