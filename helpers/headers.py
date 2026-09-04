"""What every answer of this process carries, which is the part of a page that a browser enforces instead of trusting."""

from fastapi import FastAPI, Request
from starlette.responses import Response

from helpers.settings import settings

# A login drawn inside somebody else's page is a login somebody else collects, and a type the browser guesses is a file it may run.
CARRIED = {"X-Frame-Options": "SAMEORIGIN", "X-Content-Type-Options": "nosniff", "Referrer-Policy": "strict-origin-when-cross-origin"}

PRIVATE = "private, no-store"


def lasting(scheme: str, seconds: int) -> str | None:
    """What a browser is told about http for this host, which is nothing at all where this installation is not the one served over https."""
    return f"max-age={seconds}" if scheme == "https" and seconds else None


def off_the_disk(path: str) -> bool:
    """A file served straight off the disk never depends on who asked, and telling a browser not to keep one would fetch every image of every page again."""
    return any(path == prefix or path.startswith(f"{prefix}/") for prefix in (settings.storage.base_url, settings.site.assets_url))


def for_one_reader(request: Request, answer: Response) -> bool:
    """Whether the request said who is asking or the answer says so, either of which makes this an answer a shared cache must never hand to somebody else."""
    return bool(request.cookies.get(settings.site.session_cookie) or request.headers.get("authorization") or "set-cookie" in answer.headers)


# A site reached once over http is a site somebody stood in the middle of, and only the browser can refuse the second time.
LASTING = lasting(settings.site.scheme, settings.site.hsts_max_age)


def setup(app: FastAPI):
    @app.middleware("http")
    async def carry_headers(request: Request, call_next):
        answer = await call_next(request)
        answer.headers.update(CARRIED)

        if LASTING is not None:
            answer.headers["Strict-Transport-Security"] = LASTING

        if not off_the_disk(request.url.path) and for_one_reader(request, answer):
            answer.headers["Cache-Control"] = PRIVATE

        return answer
