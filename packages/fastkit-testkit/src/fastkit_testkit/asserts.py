class EnvelopeAssertionError(AssertionError):
    pass


def assert_success(envelope: dict) -> dict:
    """Assert the envelope is a success and return its data."""

    if not envelope.get("success"):
        raise EnvelopeAssertionError(f"expected a success envelope, got {envelope.get('message')}")

    return envelope.get("data")


def assert_error(envelope: dict, code: str | None = None) -> dict:
    """Assert the envelope is an error, optionally matching a message code."""

    if envelope.get("success"):
        raise EnvelopeAssertionError("expected an error envelope, got success")

    message = envelope.get("message") or {}

    if code is not None and message.get("code") != code:
        raise EnvelopeAssertionError(f"expected error code '{code}', got '{message.get('code')}'")

    return envelope


def assert_field_error(envelope: dict, field: str) -> dict:
    """Assert the envelope carries a field error for the given field."""

    for error in envelope.get("errors", []):
        if error.get("field") == field:
            return error

    raise EnvelopeAssertionError(f"no field error found for '{field}'")
