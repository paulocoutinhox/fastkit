from typing import Protocol


class RecaptchaClient(Protocol):
    async def verify(self, token: str) -> dict: ...
