class StaticRecaptchaClient:
    """Returns a fixed provider response, used for local development and tests."""

    def __init__(self, response: dict):
        self._response = response

    async def verify(self, token: str) -> dict:
        return dict(self._response)
