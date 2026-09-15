"""What another machine answered, which is read as a map or as nothing at all."""

import httpx


def body_of(answer: httpx.Response) -> dict:
    """The body of a call to somebody else, where anything this side cannot read weighs the same as an empty answer."""
    try:
        body = answer.json()
    except ValueError:
        return {}

    return body if isinstance(body, dict) else {}
