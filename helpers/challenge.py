"""What a form has to draw, where the answer never leaves the server and only a keyed proof of it does."""

from dataclasses import dataclass

from enums.captcha_provider import CaptchaProvider as Kind


@dataclass(frozen=True)
class Challenge:
    kind: Kind
    token: str = ""
    image: str = ""
    site_key: str = ""
