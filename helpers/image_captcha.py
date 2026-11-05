"""The letters are drawn here and a proof of them travels back signed, so nothing has to be kept between the two requests and the page never carries the answer."""

import base64
import hmac
import random
import secrets
import string
from io import BytesIO

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from enums.captcha_provider import CaptchaProvider as Kind
from helpers.captcha_contract import Captcha
from helpers.challenge import Challenge
from helpers.settings import settings
from helpers.signing import digest, sign, unsign

# The two the eye confuses are left out, because a challenge nobody can read is a form nobody can send.
ALPHABET = "".join(sorted(set(string.ascii_uppercase + string.digits) - set("O0I1")))


SIZE = (200, 64)


# The bundled font is scaled instead of a system one, because a machine that has no truetype file still has to draw a readable word.
FONT = ImageFont.load_default(size=34)


class ImageCaptcha(Captcha):
    kind = Kind.IMAGE

    def issue(self) -> Challenge:
        # The word is what the challenge is, so it is drawn where nothing about it can be worked out from the words drawn before.
        word = "".join(secrets.choice(ALPHABET) for _ in range(settings.captcha.length))

        # A signed value is readable by whoever holds it, so the token carries a keyed digest of the word and never the word.
        nonce = secrets.token_urlsafe(8)

        return Challenge(kind=self.kind, token=sign("captcha", {"nonce": nonce, "proof": self.proof(nonce, word)}, settings.captcha.ttl), image=self.draw(word))

    def proof(self, nonce: str, word: str) -> str:
        return digest("captcha-word", f"{nonce}.{word}")

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

        return hmac.compare_digest(payload["proof"], self.proof(payload["nonce"], answer.strip().upper()))
