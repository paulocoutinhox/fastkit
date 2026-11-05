"""The captcha contract used by the application."""

from abc import ABC, abstractmethod

from enums.captcha_provider import CaptchaProvider as Kind
from helpers.challenge import Challenge


class Captcha(ABC):
    """A challenge is drawn and answered by the same provider, so the two halves never disagree about what was asked."""

    kind: Kind

    @abstractmethod
    def issue(self) -> Challenge: ...

    @abstractmethod
    async def verify(self, answer: str | None, token: str | None, remote_ip: str | None) -> bool: ...
