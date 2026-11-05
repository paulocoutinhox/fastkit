"""The mailer contract used by the application."""

from abc import ABC, abstractmethod

from config.email_settings import EmailSettings
from helpers.letter import Letter


class Mailer(ABC):
    """One service carries the mail of an environment, and the account it sends through is what the settings of that tenant declare."""

    @abstractmethod
    async def send(self, config: EmailSettings, letter: Letter) -> None: ...
