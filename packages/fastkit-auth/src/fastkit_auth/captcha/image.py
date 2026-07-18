import base64
import io
import json
import secrets
import string
from datetime import datetime, timedelta, timezone

from fastkit_core.api.envelope import success_envelope
from fastkit_core.errors.exceptions import AuthenticationError
from fastkit_auth.captcha.provider import CaptchaProvider
from fastkit_auth.errors import CAPTCHA_EXPIRED, CAPTCHA_INVALID, CAPTCHA_REQUIRED

_ALPHABET = string.ascii_uppercase + string.digits
_STORE_GRACE_SECONDS = 60


class ImageCaptchaProvider(CaptchaProvider):
    """A minimal self-hosted alphanumeric image captcha.

    Challenges live in the shared key-value store, so a challenge issued by one worker is verifiable
    by any worker. The browser fetches a fresh challenge (id + PNG data URI) and submits
    ``{"challenge_id": ..., "answer": ...}`` with the login.
    """

    name = "image"

    def __init__(self, store, length: int = 5, ttl_seconds: int = 300, clock=None):
        self._store = store
        self._length = length
        self._ttl_seconds = ttl_seconds
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    @property
    def enabled(self) -> bool:
        return True

    def _store_key(self, challenge_id: str) -> str:
        return f"auth:captcha:image:{challenge_id}"

    async def new_challenge(self) -> dict:
        code = "".join(secrets.choice(_ALPHABET) for _ in range(self._length))
        challenge_id = secrets.token_urlsafe(16)
        expires_at = self._clock() + timedelta(seconds=self._ttl_seconds)
        payload = json.dumps({"code": code, "expires_at": expires_at.isoformat()})

        await self._store.set(
            self._store_key(challenge_id),
            payload.encode("utf-8"),
            ttl=self._ttl_seconds + _STORE_GRACE_SECONDS,
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

        stored = await self._store.get(self._store_key(challenge_id))

        if stored is None:
            raise AuthenticationError(
                CAPTCHA_INVALID, message="captcha challenge is unknown"
            )

        await self._store.delete(self._store_key(challenge_id))
        data = json.loads(stored.decode("utf-8"))

        if datetime.fromisoformat(data["expires_at"]) <= self._clock():
            raise AuthenticationError(
                CAPTCHA_EXPIRED, message="captcha challenge expired"
            )

        if str(answer).strip().upper() != data["code"]:
            raise AuthenticationError(
                CAPTCHA_INVALID, message="captcha answer is incorrect"
            )

    def client_config(self) -> dict:
        return {"provider": "image", "enabled": True, "new_url": "/auth/captcha/new"}

    def mount_routes(self, router) -> None:
        @router.get("/auth/captcha/new")
        async def new_captcha():
            return success_envelope(data=await self.new_challenge())

    def _render(self, code: str) -> str:
        from PIL import Image, ImageDraw

        image = Image.new("RGB", (34 * self._length, 60), (246, 248, 250))
        draw = ImageDraw.Draw(image)

        for index, char in enumerate(code):
            draw.text((14 + index * 34, 22), char, fill=(33, 37, 41))

        buffer = io.BytesIO()
        image.save(buffer, format="PNG")

        return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()
