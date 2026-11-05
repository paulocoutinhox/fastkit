"""Short-lived browser binding for social callbacks and admin session handoff."""

import hashlib

from fastapi import Response

from enums.social_provider import SocialProvider
from helpers import cookies
from helpers.settings import settings


class AuthenticationCookieHelper:
    @staticmethod
    def name(token: str) -> str:
        suffix = hashlib.sha256(token.encode()).hexdigest()[:24]

        return f"{settings.site.authentication_cookie_prefix}-{suffix}"

    @staticmethod
    def remember(response: Response, token: str, browser: str, ttl: int, provider: SocialProvider | None = None) -> None:
        cookies.remember(response, AuthenticationCookieHelper.name(token), browser, ttl, cross_site_post=provider == SocialProvider.APPLE)

    @staticmethod
    def forget(response: Response, token: str) -> None:
        cookies.forget(response, AuthenticationCookieHelper.name(token))
