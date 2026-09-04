"""The ceiling on a body this process parses into memory, because one request is otherwise enough to take a node down."""

import inspect

from fastapi import FastAPI, UploadFile
from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.routing import compile_path
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from helpers.errors import build_payload
from helpers.i18n import translate
from helpers.settings import settings

STREAMED = "multipart/form-data"

CODE = "error.payload-too-large"


def takes_a_file(endpoint) -> bool:
    return any(parameter.annotation is UploadFile for parameter in inspect.signature(endpoint).parameters.values())


def streaming_paths(app) -> list:
    """The addresses that take a file, read off the application because a header is what the caller chose to send."""
    found = []

    for included in app.routes:
        context = getattr(included, "include_context", None)
        prefix = context.prefix if context else ""

        for route in getattr(getattr(included, "original_router", None), "routes", [included]):
            if getattr(route, "endpoint", None) and takes_a_file(route.endpoint):
                found.append(compile_path(f"{prefix}{route.path}")[0])

    return found


class BodyLimit:
    """A body that says how long it is answers for that, and one that does not is counted while it arrives."""

    def __init__(self, app: ASGIApp, limit: int):
        self.app = app
        self.limit = limit
        self.streaming = None

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)

            return

        headers = Headers(scope=scope)

        if STREAMED in headers.get("content-type", "") and self.streams(scope):
            await self.app(scope, receive, send)

            return

        declared = headers.get("content-length", "")

        if declared.isdigit():
            # The server delivers no more than it was told, so the number is the size and nothing has to be held to know it.
            if int(declared) > self.limit:
                await self.refuse(scope, receive, send)

                return

            await self.app(scope, receive, send)

            return

        if not headers.get("transfer-encoding"):
            await self.app(scope, receive, send)

            return

        body, whole = await self.taken(receive)

        if not whole:
            await self.refuse(scope, receive, send)

            return

        await self.app(scope, self.replayed(body, receive), send)

    def streams(self, scope: Scope) -> bool:
        """Whether this address takes a file, because a body wearing the content type of one is still read whole by a route that does not."""
        if self.streaming is None:
            self.streaming = streaming_paths(scope["app"])

        return any(pattern.match(scope["path"]) for pattern in self.streaming)

    async def taken(self, receive: Receive) -> tuple[bytes, bool]:
        """What arrived, stopping at the ceiling rather than at the end, so nothing past it is ever held."""
        body = bytearray()

        while True:
            message = await receive()

            if message["type"] != "http.request":
                return bytes(body), True

            body += message.get("body", b"")

            if len(body) > self.limit:
                return b"", False

            if not message.get("more_body"):
                return bytes(body), True

    def replayed(self, body: bytes, receive: Receive) -> Receive:
        sent = False

        async def replay() -> Message:
            nonlocal sent

            if sent:
                return await receive()

            sent = True

            return {"type": "http.request", "body": body, "more_body": False}

        return replay

    async def refuse(self, scope: Scope, receive: Receive, send: Send) -> None:
        answer = JSONResponse(status_code=413, content=build_payload(CODE, translate(CODE)))

        await answer(scope, receive, send)


def setup(app: FastAPI):
    app.add_middleware(BodyLimit, limit=settings.request_max_bytes)
