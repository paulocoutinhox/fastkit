"""The language of a request, fixed for as long as that request is being answered."""

from fastapi import FastAPI, Request

from helpers.i18n import current_locale, resolve_locale


def setup(app: FastAPI):
    @app.middleware("http")
    async def apply_locale(request: Request, call_next):
        """Every message leaving the request is rendered in the language the caller asked for."""
        token = current_locale.set(resolve_locale(request.headers.get("accept-language")))

        try:
            return await call_next(request)
        finally:
            current_locale.reset(token)
