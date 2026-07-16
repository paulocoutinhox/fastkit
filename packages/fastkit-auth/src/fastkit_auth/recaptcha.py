from dataclasses import dataclass
from typing import Protocol

from fastkit_core.errors.exceptions import AuthenticationError
from fastkit_auth.errors import (
    RECAPTCHA_ACTION_MISMATCH,
    RECAPTCHA_HOSTNAME_MISMATCH,
    RECAPTCHA_INVALID,
    RECAPTCHA_LOW_SCORE,
    RECAPTCHA_MISSING,
    RECAPTCHA_PROVIDER_UNAVAILABLE,
)


@dataclass(frozen=True)
class RecaptchaConfig:
    enabled: bool
    action: str
    minimum_score: float
    allowed_hostnames: tuple[str, ...]


class RecaptchaClient(Protocol):
    async def verify(self, token: str) -> dict:
        ...


class StaticRecaptchaClient:
    """Returns a fixed provider response, used for local development and tests."""

    def __init__(self, response: dict):
        self._response = response

    async def verify(self, token: str) -> dict:
        return dict(self._response)


class GoogleRecaptchaClient:
    """Verifies a token against the Google reCAPTCHA v3 siteverify endpoint."""

    endpoint = "https://www.google.com/recaptcha/api/siteverify"

    def __init__(self, secret_key: str, timeout_seconds: int = 5):
        self._secret_key = secret_key
        self._timeout_seconds = timeout_seconds

    async def verify(self, token: str) -> dict:
        import httpx

        async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
            response = await client.post(self.endpoint, data={"secret": self._secret_key, "response": token})

            return response.json()


class RecaptchaVerifier:
    """Validates a reCAPTCHA v3 token against success, score, action and hostname."""

    def __init__(self, config: RecaptchaConfig, client: RecaptchaClient):
        self._config = config
        self._client = client
        self._used_tokens: set[str] = set()

    async def verify(self, token: str | None) -> None:
        if not self._config.enabled:
            return

        if not token:
            raise AuthenticationError(RECAPTCHA_MISSING, message="recaptcha token is required")

        if token in self._used_tokens:
            raise AuthenticationError(RECAPTCHA_INVALID, message="recaptcha token was already used")

        self._used_tokens.add(token)

        response = await self._call_provider(token)
        self._validate_response(response)

    async def _call_provider(self, token: str) -> dict:
        try:
            return await self._client.verify(token)
        except Exception as error:
            raise AuthenticationError(RECAPTCHA_PROVIDER_UNAVAILABLE, message="recaptcha provider is unavailable") from error

    def _validate_response(self, response: dict) -> None:
        if not response.get("success"):
            raise AuthenticationError(RECAPTCHA_INVALID, message="recaptcha verification failed")

        if response.get("action") != self._config.action:
            raise AuthenticationError(RECAPTCHA_ACTION_MISMATCH, message="recaptcha action mismatch")

        if self._config.allowed_hostnames and response.get("hostname") not in self._config.allowed_hostnames:
            raise AuthenticationError(RECAPTCHA_HOSTNAME_MISMATCH, message="recaptcha hostname mismatch")

        if float(response.get("score", 0.0)) < self._config.minimum_score:
            raise AuthenticationError(RECAPTCHA_LOW_SCORE, message="recaptcha score too low")
