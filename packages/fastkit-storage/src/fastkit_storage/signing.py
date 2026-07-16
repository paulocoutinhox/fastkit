import hashlib
import hmac


def sign(secret: str, key: str, expires_at: int, method: str) -> str:
    message = f"{method}:{key}:{expires_at}".encode("utf-8")

    return hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()


def verify(secret: str, key: str, expires_at: int, method: str, signature: str, now: int) -> bool:
    if now > expires_at:
        return False

    expected = sign(secret, key, expires_at, method)

    return hmac.compare_digest(expected, signature)
