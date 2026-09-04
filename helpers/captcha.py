"""The challenge a public form carries, and the providers an environment picks one of."""

import base64
import random
import secrets
import string
from abc import ABC, abstractmethod
from dataclasses import dataclass
from io import BytesIO

import httpx
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from enums.captcha import CaptchaProvider as Kind
from helpers import remote
from helpers.settings import settings
from helpers.signing import sign, unsign

SITE_VERIFY = "https://www.google.com/recaptcha/api/siteverify"

TIMEOUT = 5.0

# The two the eye confuses are left out, because a challenge nobody can read is a form nobody can send.
ALPHABET = "".join(sorted(set(string.ascii_uppercase + string.digits) - set("O0I1")))

SIZE = (200, 64)

# The bundled font is scaled instead of a system one, because a machine that has no truetype file still has to draw a readable word.
FONT = ImageFont.load_default(size=34)


@dataclass(frozen=True)
class Challenge:
    """What a form has to draw, where the half that proves the answer never leaves the server."""

    kind: Kind
    token: str = ""
    image: str = ""
    site_key: str = ""


class Captcha(ABC):
    """A challenge is drawn and answered by the same provider, so the two halves never disagree about what was asked."""

    kind: Kind

    @abstractmethod
    def issue(self) -> Challenge: ...

    @abstractmethod
    async def verify(self, answer: str | None, token: str | None, remote_ip: str | None) -> bool: ...


class DisabledCaptcha(Captcha):
    """What an environment chooses when there is nobody to keep out, which is a decision and never what a failure falls back to."""

    kind = Kind.DISABLED

    def issue(self) -> Challenge:
        return Challenge(kind=self.kind)

    async def verify(self, answer: str | None, token: str | None, remote_ip: str | None) -> bool:
        return True


class ImageCaptcha(Captcha):
    """The letters are drawn here and travel back signed, so nothing has to be kept between the two requests."""

    kind = Kind.IMAGE

    def issue(self) -> Challenge:
        # The word is what the challenge is, so it is drawn where nothing about it can be worked out from the words drawn before.
        word = "".join(secrets.choice(ALPHABET) for _ in range(settings.captcha.length))

        return Challenge(kind=self.kind, token=sign("captcha", {"word": word}, settings.captcha.ttl), image=self.draw(word))

    def draw(self, word: str) -> str:
        """The word as a picture, on a background of noise that only has to be messy and never has to be unguessable."""
        image = Image.new("RGB", SIZE, (248, 250, 252))
        drawing = ImageDraw.Draw(image)

        for _ in range(6):
            drawing.line([(random.randint(0, SIZE[0]), random.randint(0, SIZE[1])) for _ in range(2)], fill=(203, 213, 225), width=2)

        for position, letter in enumerate(word):
            drawing.text((16 + position * 34 + random.randint(-3, 3), 12 + random.randint(-6, 6)), letter, font=FONT, fill=(30, 41, 59))

        for _ in range(400):
            image.putpixel((random.randint(0, SIZE[0] - 1), random.randint(0, SIZE[1] - 1)), (148, 163, 184))

        buffer = BytesIO()
        image.filter(ImageFilter.SMOOTH).save(buffer, "PNG")

        return f"data:image/png;base64,{base64.b64encode(buffer.getvalue()).decode()}"

    async def verify(self, answer: str | None, token: str | None, remote_ip: str | None) -> bool:
        payload = unsign("captcha", token)

        if payload is None or not answer:
            return False

        return answer.strip().upper() == payload["word"]


class RecaptchaV3(Captcha):
    """Google scores the visit instead of asking anything, so the page only has to carry the site key."""

    kind = Kind.RECAPTCHA_V3

    def issue(self) -> Challenge:
        return Challenge(kind=self.kind, site_key=settings.captcha.site_key)

    async def verify(self, answer: str | None, token: str | None, remote_ip: str | None) -> bool:
        if not answer:
            return False

        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            answered = await client.post(SITE_VERIFY, data={"secret": settings.captcha.secret_key, "response": answer, "remoteip": remote_ip or ""})

        # A network that did not answer is not a visitor that passed, so anything but a clean answer is a refusal.
        if answered.status_code != httpx.codes.OK:
            return False

        body = remote.body_of(answered)

        return bool(body.get("success")) and self.scored(body) >= settings.captcha.score_threshold

    def scored(self, body: dict) -> float:
        """A score nothing can read is not a visitor that passed, so it weighs as the lowest one there is."""
        try:
            return float(body.get("score", 0))
        except (TypeError, ValueError):
            return 0.0


PROVIDERS: dict[Kind, Captcha] = {Kind.DISABLED: DisabledCaptcha(), Kind.IMAGE: ImageCaptcha(), Kind.RECAPTCHA_V3: RecaptchaV3()}


def current() -> Captcha:
    return PROVIDERS[Kind(settings.captcha.provider)]


def issue() -> Challenge:
    return current().issue()


async def verify(answer: str | None, token: str | None, remote_ip: str | None) -> bool:
    return await current().verify(answer, token, remote_ip)
