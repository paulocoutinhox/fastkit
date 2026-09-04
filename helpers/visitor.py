"""The name a reader is counted by, handed out signed and kept only where somebody allowed it to be kept."""

import secrets

from starlette.requests import Request
from starlette.responses import Response

from enums.consent import ConsentCategory
from helpers import cookies
from helpers.consent import given
from helpers.settings import settings
from helpers.signing import sign, unsign


def minted() -> str:
    """A name this side signs and never stores, so counting a reader needs no row and no session shared between copies."""
    return sign("visitor", {"visitor": secrets.token_urlsafe(16)}, settings.site.visitor_max_age)


def named(value: str | None) -> str | None:
    """The name inside a signed value, and nothing at all where the signature does not hold."""
    payload = unsign("visitor", value)

    return payload.get("visitor") if payload else None


def remember(response: Response, value: str) -> None:
    cookies.remember(response, settings.site.visitor_cookie, value, settings.site.visitor_max_age)


def carried(request: Request) -> str:
    """The signed name this browser already carries, or a fresh one where it carries none that this server wrote."""
    value = request.cookies.get(settings.site.visitor_cookie)

    return value if named(value) is not None else minted()


def forget(response: Response) -> None:
    cookies.forget(response, settings.site.visitor_cookie)


def counted(request: Request) -> str | None:
    """Who this request counts as, which is nobody at all until somebody allowed analytics to be kept."""
    if ConsentCategory.ANALYTICS not in given(request).allowed:
        return None

    return named(request.cookies.get(settings.site.visitor_cookie))
