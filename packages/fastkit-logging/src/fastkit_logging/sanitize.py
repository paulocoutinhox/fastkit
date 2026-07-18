SENSITIVE_KEYS = frozenset(
    {
        "password",
        "passphrase",
        "token",
        "cookie",
        "authorization",
        "bearer",
        "secret",
        "credential",
        "apikey",
        "api_key",
        "card_number",
        "cardnumber",
        "cardholder",
        "cvv",
        "ssn",
        "private_key",
    }
)

REDACTED = "***"

_MAX_DEPTH = 8


def _is_sensitive(key: str) -> bool:
    lowered = key.lower()

    return any(marker in lowered for marker in SENSITIVE_KEYS)


def sanitize(value, _depth: int = 0):
    """Recursively redact sensitive keys so credentials never reach a log sink."""

    if _depth > _MAX_DEPTH:
        return REDACTED if isinstance(value, (dict, list, tuple)) else value

    if isinstance(value, dict):
        return {
            key: (REDACTED if _is_sensitive(key) else sanitize(item, _depth + 1))
            for key, item in value.items()
        }

    if isinstance(value, (list, tuple)):
        return [sanitize(item, _depth + 1) for item in value]

    return value
