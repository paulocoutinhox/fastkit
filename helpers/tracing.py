"""The name a request answers to, which is what ties a log line, an audit row and a reported failure to the same call."""

import re
import uuid
from contextvars import ContextVar

from fastapi import FastAPI, Request

HEADER = "X-Request-Id"

# What a caller may name a request, kept short and printable so it reaches a log line as it was written.
ACCEPTED = re.compile(r"^[A-Za-z0-9._-]{8,64}$")

current_request: ContextVar[str] = ContextVar("current_request", default="")


def named(given: str | None) -> str:
    """The name the caller gave when it is one this can carry, and a fresh one when it is not."""
    return given if given and ACCEPTED.match(given) else uuid.uuid4().hex


def setup(app: FastAPI):
    @app.middleware("http")
    async def carry_request_name(request: Request, call_next):
        name = named(request.headers.get(HEADER))
        token = current_request.set(name)

        try:
            answer = await call_next(request)
        finally:
            current_request.reset(token)

        answer.headers[HEADER] = name

        return answer
