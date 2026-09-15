"""A HEAD is a GET whose body is dropped, which is what a crawler, a link checker and an uptime monitor ask with first."""

from fastapi import FastAPI
from starlette.types import ASGIApp, Receive, Scope, Send


class AnswerHeadAsGet:
    """The route table declares what it publishes, so the method is rewritten here instead of doubling every entry of the schema."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope["method"] == "HEAD":
            scope = {**scope, "method": "GET"}

        await self.app(scope, receive, send)


def setup(app: FastAPI) -> None:
    app.add_middleware(AnswerHeadAsGet)
