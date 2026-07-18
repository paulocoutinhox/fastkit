import base64
import io
import secrets
import string
from datetime import datetime, timedelta, timezone

from fastkit_core.api.envelope import success_envelope
from fastkit_core.errors.exceptions import AuthenticationError
from fastkit_auth.captcha.provider import CaptchaProvider
from fastkit_auth.errors import CAPTCHA_EXPIRED, CAPTCHA_INVALID, CAPTCHA_REQUIRED

_ALPHABET = string.ascii_uppercase + string.digits


class ImageCaptchaProvider(CaptchaProvider):
    """A minimal self-hosted alphanumeric image captcha, shipped as an example and for tests.

    Challenges live in-process (single-worker only) — a multi-worker deployment wants a shared store,
    like the rate limiter. The browser fetches a fresh challenge (id + PNG data URI) and submits
    ``{"challenge_id": ..., "answer": ...}`` with the login.
    """

    name = "image"

    def __init__(self, length: int = 5, ttl_seconds: int = 300, clock=None):
        self._length = length
        self._ttl_seconds = ttl_seconds
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._challenges: dict[str, tuple[str, datetime]] = {}

    @property
    def enabled(self) -> bool:
        return True

    def new_challenge(self) -> dict:
        code = "".join(secrets.choice(_ALPHABET) for _ in range(self._length))
        challenge_id = secrets.token_urlsafe(16)
        self._challenges[challenge_id] = (
            code,
            self._clock() + timedelta(seconds=self._ttl_seconds),
        )

        return {"challenge_id": challenge_id, "image": self._render(code)}

    async def verify(self, payload: dict | None) -> None:
        payload = payload or {}
        challenge_id = payload.get("challenge_id")
        answer = payload.get("answer")

        if not challenge_id or not answer:
            raise AuthenticationError(
                CAPTCHA_REQUIRED, message="captcha answer is required"
            )

        entry = self._challenges.pop(challenge_id, None)

        if entry is None:
            raise AuthenticationError(
                CAPTCHA_INVALID, message="captcha challenge is unknown"
            )

        code, expires_at = entry

        if expires_at <= self._clock():
            raise AuthenticationError(
                CAPTCHA_EXPIRED, message="captcha challenge expired"
            )

        if str(answer).strip().upper() != code:
            raise AuthenticationError(
                CAPTCHA_INVALID, message="captcha answer is incorrect"
            )

    def client_config(self) -> dict:
        return {"provider": "image", "enabled": True, "new_url": "/auth/captcha/new"}

    def mount_routes(self, router) -> None:
        @router.get("/auth/captcha/new")
        async def new_captcha():
            return success_envelope(data=self.new_challenge())

    def _render(self, code: str) -> str:
        from PIL import Image, ImageDraw

        image = Image.new("RGB", (34 * self._length, 60), (246, 248, 250))
        draw = ImageDraw.Draw(image)

        for index, char in enumerate(code):
            draw.text((14 + index * 34, 22), char, fill=(33, 37, 41))

        buffer = io.BytesIO()
        image.save(buffer, format="PNG")

        return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()
