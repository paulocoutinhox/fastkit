"""The route table declares what it publishes, so the method is rewritten here instead of doubling every entry of the schema."""

from starlette.types import ASGIApp, Receive, Scope, Send


class AnswerHeadAsGet:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope["method"] == "HEAD":
            scope = {**scope, "method": "GET"}

        await self.app(scope, receive, send)
