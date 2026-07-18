from dataclasses import dataclass
from typing import Protocol

from fastkit_core.errors.exceptions import AuthenticationError
from fastkit_auth.captcha.provider import CaptchaProvider
from fastkit_auth.errors import (
    CAPTCHA_INVALID,
    CAPTCHA_PROVIDER_UNAVAILABLE,
    CAPTCHA_REQUIRED,
)


@dataclass(frozen=True)
class RecaptchaConfig:
    action: str
    minimum_score: float
    allowed_hostnames: tuple[str, ...]


class RecaptchaClient(Protocol):
    async def verify(self, token: str) -> dict: ...


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
            response = await client.post(
                self.endpoint, data={"secret": self._secret_key, "response": token}
            )

            return response.json()


class RecaptchaProvider(CaptchaProvider):
    """reCAPTCHA v3: the browser loads Google's script and submits a token; verification checks
    success, score, action and hostname against the siteverify response."""

    name = "recaptcha"

    def __init__(self, config: RecaptchaConfig, client: RecaptchaClient, site_key: str):
        self._config = config
        self._client = client
        self._site_key = site_key
        self._used_tokens: set[str] = set()

    @property
    def enabled(self) -> bool:
        return True

    async def verify(self, payload: dict | None) -> None:
        token = (payload or {}).get("token")

        if not token:
            raise AuthenticationError(
                CAPTCHA_REQUIRED, message="captcha token is required"
            )

        if token in self._used_tokens:
            raise AuthenticationError(
                CAPTCHA_INVALID, message="captcha token was already used"
            )

        self._used_tokens.add(token)

        response = await self._call_provider(token)
        self._validate_response(response)

    async def _call_provider(self, token: str) -> dict:
        try:
            return await self._client.verify(token)
        except Exception as error:
            raise AuthenticationError(
                CAPTCHA_PROVIDER_UNAVAILABLE, message="captcha provider is unavailable"
            ) from error

    def _validate_response(self, response: dict) -> None:
        if not response.get("success"):
            raise AuthenticationError(
                CAPTCHA_INVALID, message="captcha verification failed"
            )

        if response.get("action") != self._config.action:
            raise AuthenticationError(
                CAPTCHA_INVALID, message="captcha action mismatch"
            )

        if (
            self._config.allowed_hostnames
            and response.get("hostname") not in self._config.allowed_hostnames
        ):
            raise AuthenticationError(
                CAPTCHA_INVALID, message="captcha hostname mismatch"
            )

        if float(response.get("score", 0.0)) < self._config.minimum_score:
            raise AuthenticationError(CAPTCHA_INVALID, message="captcha score too low")

    def client_config(self) -> dict:
        return {
            "provider": "recaptcha",
            "enabled": True,
            "site_key": self._site_key,
            "action": self._config.action,
            "script_url": f"https://www.google.com/recaptcha/api.js?render={self._site_key}",
        }
