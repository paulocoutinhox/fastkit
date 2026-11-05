"""The challenge a public form carries, and the providers an environment picks one of."""

from enums.captcha_provider import CaptchaProvider as Kind
from helpers.captcha_contract import Captcha
from helpers.challenge import Challenge
from helpers.disabled_captcha import DisabledCaptcha
from helpers.image_captcha import ImageCaptcha
from helpers.recaptcha_v3 import RecaptchaV3
from helpers.settings import settings

PROVIDERS: dict[Kind, Captcha] = {Kind.DISABLED: DisabledCaptcha(), Kind.IMAGE: ImageCaptcha(), Kind.RECAPTCHA_V3: RecaptchaV3()}


def current() -> Captcha:
    return PROVIDERS[settings.captcha.provider]


def issue() -> Challenge:
    return current().issue()


async def verify(answer: str | None, token: str | None, remote_ip: str | None) -> bool:
    return await current().verify(answer, token, remote_ip)
