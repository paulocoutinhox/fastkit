"""Google scores the visit instead of asking anything, so the page only has to carry the site key."""

import httpx2

from enums.captcha_provider import CaptchaProvider as Kind
from helpers import remote
from helpers.captcha_contract import Captcha
from helpers.challenge import Challenge
from helpers.settings import settings

SITE_VERIFY = "https://www.google.com/recaptcha/api/siteverify"


TIMEOUT = 5.0


class RecaptchaV3(Captcha):
    kind = Kind.RECAPTCHA_V3

    def issue(self) -> Challenge:
        return Challenge(kind=self.kind, site_key=settings.captcha.site_key)

    async def verify(self, answer: str | None, token: str | None, remote_ip: str | None) -> bool:
        if not answer:
            return False

        # A network that did not answer is not a visitor that passed, so anything but a clean answer is a refusal.
        try:
            async with httpx2.AsyncClient(timeout=TIMEOUT) as client:
                answered = await client.post(SITE_VERIFY, data={"secret": settings.captcha.secret_key, "response": answer, "remoteip": remote_ip or ""})
        except httpx2.HTTPError:
            return False

        if answered.status_code != httpx2.codes.OK:
            return False

        body = remote.body_of(answered)

        return bool(body.get("success")) and self.scored(body) >= settings.captcha.score_threshold

    def scored(self, body: dict) -> float:
        """A score nothing can read is not a visitor that passed, so it weighs as the lowest one there is."""
        try:
            return float(body.get("score", 0))
        except (TypeError, ValueError):
            return 0.0
