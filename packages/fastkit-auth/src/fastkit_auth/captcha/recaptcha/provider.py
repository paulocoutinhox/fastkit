import hashlib

from fastkit_core.errors.exceptions import AuthenticationError
from fastkit_auth.captcha.provider import CaptchaProvider
from fastkit_auth.captcha.recaptcha.client import RecaptchaClient
from fastkit_auth.captcha.recaptcha.config import RecaptchaConfig
from fastkit_auth.errors import (
    CAPTCHA_INVALID,
    CAPTCHA_PROVIDER_UNAVAILABLE,
    CAPTCHA_REQUIRED,
)


class RecaptchaProvider(CaptchaProvider):
    """reCAPTCHA v3: the browser loads Google's script and submits a token; verification checks
    success, score, action and hostname against the siteverify response.

    Used tokens live in the shared key-value store, so a replayed token is rejected across every
    worker in a multi-worker deployment, not only the one that first saw it.
    """

    name = "recaptcha"

    def __init__(
        self,
        config: RecaptchaConfig,
        client: RecaptchaClient,
        site_key: str,
        store,
        token_ttl_seconds: int = 300,
    ):
        self._config = config
        self._client = client
        self._site_key = site_key
        self._store = store
        self._token_ttl_seconds = token_ttl_seconds

    @property
    def enabled(self) -> bool:
        return True

    def _used_key(self, token: str) -> str:
        digest = hashlib.sha256(token.encode("utf-8")).hexdigest()

        return f"auth:captcha:recaptcha:used:{digest}"

    async def verify(self, payload: dict | None) -> None:
        token = (payload or {}).get("token")

        if not token:
            raise AuthenticationError(
                CAPTCHA_REQUIRED, message="captcha token is required"
            )

        used_key = self._used_key(token)

        if await self._store.get(used_key) is not None:
            raise AuthenticationError(
                CAPTCHA_INVALID, message="captcha token was already used"
            )

        await self._store.set(used_key, b"1", ttl=self._token_ttl_seconds)

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

        try:
            score = float(response.get("score", 0.0))
        except (TypeError, ValueError) as error:
            raise AuthenticationError(
                CAPTCHA_INVALID, message="captcha score invalid"
            ) from error

        if score < self._config.minimum_score:
            raise AuthenticationError(CAPTCHA_INVALID, message="captcha score too low")

    def client_config(self) -> dict:
        return {
            "provider": "recaptcha",
            "enabled": True,
            "site_key": self._site_key,
            "action": self._config.action,
            "script_url": f"https://www.google.com/recaptcha/api.js?render={self._site_key}",
        }
