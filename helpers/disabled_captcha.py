"""What an environment chooses when there is nobody to keep out, which is a decision and never what a failure falls back to."""

from enums.captcha_provider import CaptchaProvider as Kind
from helpers.captcha_contract import Captcha
from helpers.challenge import Challenge


class DisabledCaptcha(Captcha):
    kind = Kind.DISABLED

    def issue(self) -> Challenge:
        return Challenge(kind=self.kind)

    async def verify(self, answer: str | None, token: str | None, remote_ip: str | None) -> bool:
        return True
