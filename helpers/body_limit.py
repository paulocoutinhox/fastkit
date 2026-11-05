"""Request body limits enforced while bytes arrive, with a larger ceiling for upload routes."""

import inspect
from typing import get_args

from fastapi import UploadFile
from fastapi.routing import iter_route_contexts
from starlette.datastructures import Headers
from starlette.middleware.body_limit import RequestBodyLimitMiddleware
from starlette.responses import JSONResponse
from starlette.routing import compile_path
from starlette.types import ASGIApp, Receive, Scope, Send

from helpers.errors import build_payload
from helpers.i18n import translate
from helpers.settings import settings

STREAMED = "multipart/form-data"


CODE = "error.payload-too-large"


def takes_a_file(endpoint) -> bool:
    return any(names_a_file(parameter.annotation) for parameter in inspect.signature(endpoint).parameters.values())


def names_a_file(annotation) -> bool:
    """Whether an annotation carries an upload anywhere inside it, which is how a file is also declared as optional, as a list or through `Annotated`."""
    if annotation is UploadFile:
        return True

    return any(names_a_file(argument) for argument in get_args(annotation))


def streaming_paths(app) -> list:
    """The addresses that take a file, read off the application because a header is what the caller chose to send."""
    found = []

    for context in iter_route_contexts(app.routes):
        if context.endpoint is not None and takes_a_file(context.endpoint):
            found.append(compile_path(context.path)[0])

    return found


class BodyLimit:
    def __init__(self, app: ASGIApp, limit: int):
        self.app = app
        self.limit = limit
        self.streaming = None

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)

            return

        headers = Headers(scope=scope)
        declared = headers.get("content-length", "")

        # A file is streamed to disk before any route guard runs, so the address that takes one is bounded by the largest upload and never by nothing.
        ceiling = settings.upload_max_bytes if STREAMED in headers.get("content-type", "") and self.streams(scope) else self.limit

        if declared.isascii() and declared.isdigit() and int(declared) > ceiling:
            await self.refuse(scope, receive, send)

            return

        limited = RequestBodyLimitMiddleware(self.app, max_body_size=ceiling)

        await limited(scope, receive, send)

    def streams(self, scope: Scope) -> bool:
        """Whether this address takes a file, because a body wearing the content type of one is still read whole by a route that does not."""
        if self.streaming is None:
            self.streaming = streaming_paths(scope["app"])

        return any(pattern.match(scope["path"]) for pattern in self.streaming)

    async def refuse(self, scope: Scope, receive: Receive, send: Send) -> None:
        answer = JSONResponse(status_code=413, content=build_payload(CODE, translate(CODE)))

        await answer(scope, receive, send)
