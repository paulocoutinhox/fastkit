class GoogleRecaptchaClient:
    """Verifies a token against the Google reCAPTCHA v3 siteverify endpoint."""

    endpoint = "https://www.google.com/recaptcha/api/siteverify"

    def __init__(self, secret_key: str, timeout_seconds: int = 5):
        self._secret_key = secret_key
        self._timeout_seconds = timeout_seconds

    async def verify(self, token: str) -> dict:
        import httpx

        async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
            response = await client.post(
                self.endpoint, data={"secret": self._secret_key, "response": token}
            )

            return response.json()
