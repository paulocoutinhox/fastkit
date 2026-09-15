"""A value this side hands out and reads back without keeping it anywhere."""

import base64
import hashlib
import hmac
import json

from helpers.dates import now
from helpers.settings import settings


def digest(purpose: str, body: str) -> str:
    return hmac.new(settings.security.secret_key.encode(), f"{purpose}.{body}".encode(), hashlib.sha256).hexdigest()


def sign(purpose: str, payload: dict, ttl: int) -> str:
    """A value the server hands out and reads back without keeping it anywhere, which is what makes it survive more than one process."""
    stamped = {**payload, "exp": int(now().timestamp()) + ttl}
    body = base64.urlsafe_b64encode(json.dumps(stamped, separators=(",", ":")).encode()).decode().rstrip("=")

    return f"{body}.{digest(purpose, body)}"


def unsign(purpose: str, value: str | None) -> dict | None:
    """What was signed for this very purpose, and nothing at all where the signature does not hold or the moment has passed."""
    if not value:
        return None

    body, _, given = value.partition(".")

    # The purpose is signed with the body, so a value this server handed out for one thing never reads as another.
    if not given or not hmac.compare_digest(given.encode(), digest(purpose, body).encode()):
        return None

    payload = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))

    if payload["exp"] < now().timestamp():
        return None

    return payload
