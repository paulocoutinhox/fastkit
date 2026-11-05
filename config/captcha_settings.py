from pydantic import BaseModel

from enums.captcha_provider import CaptchaProvider


class CaptchaSettings(BaseModel):
    """Which challenge a public form carries, where `disabled` is declared by an environment and never assumed by a failure."""

    # A challenge this server draws needs no key from anybody, so an environment that says nothing still guards its public forms.
    provider: CaptchaProvider = CaptchaProvider.IMAGE
    site_key: str = ""
    secret_key: str = ""

    # What reCAPTCHA has to answer for a call to count as human.
    score_threshold: float = 0.5

    # How long a drawn challenge stays valid, which is what stops one image from answering for a whole afternoon.
    ttl: int = 600
    length: int = 5
