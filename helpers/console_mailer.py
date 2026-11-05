"""What a machine with no mail server writes instead, so a recovery link is read off the log rather than waited for."""

import logging

from config.email_settings import EmailSettings
from helpers.letter import Letter
from helpers.mailer_contract import Mailer

logger = logging.getLogger(__name__)


class ConsoleMailer(Mailer):
    async def send(self, config: EmailSettings, letter: Letter) -> None:
        logger.info("[email] from=%s to=%s subject=%s\n%s", config.from_address, letter.to, letter.subject, letter.html)
