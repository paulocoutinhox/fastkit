"""What another machine answered, which is read as a map or as nothing at all."""

import httpx


def body_of(answer: httpx.Response) -> dict:
    """The body of a call to somebody else, where anything this side cannot read weighs the same as an empty answer."""
    # A body nested deep enough stops the parser itself, which is one more way of being unreadable.
    try:
        body = answer.json()
    except (ValueError, RecursionError):
        return {}

    return body if isinstance(body, dict) else {}
