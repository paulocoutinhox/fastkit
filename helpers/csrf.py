"""The value that proves a form was drawn by this site, which travels in a cookie and in the form."""

import hmac
import secrets

from starlette.requests import Request
from starlette.responses import Response

from helpers import cookies
from helpers.settings import settings

COOKIE = "fastkit_csrf"
FIELD = "csrf_token"


def issue(request: Request) -> str:
    """The same value travels in a cookie and in the form, and only a page served from this site can read one to fill the other."""
    return request.cookies.get(COOKIE) or secrets.token_urlsafe(32)


def remember(response: Response, token: str) -> None:
    cookies.remember(response, COOKIE, token, settings.site.csrf_ttl)


def valid(request: Request, sent: str | None) -> bool:
    held = request.cookies.get(COOKIE)

    if not held or not sent:
        return False

    return hmac.compare_digest(held.encode(), sent.encode())
