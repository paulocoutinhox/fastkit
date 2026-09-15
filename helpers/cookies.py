"""How this site writes a cookie, which is one answer to who may read it and where it travels."""

from fastapi import Response

from helpers.settings import settings


def remember(response: Response, name: str, value: str, max_age: int | None = None) -> None:
    """No cookie of this site is read by a script, and none of them leaves over plain http where there is https to leave over."""
    response.set_cookie(name, value, max_age=max_age, httponly=True, secure=settings.site.cookie_secure, samesite="lax", path="/")


def forget(response: Response, name: str) -> None:
    response.delete_cookie(name, path="/")
