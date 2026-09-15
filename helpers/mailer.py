"""How a written message leaves this process, which is one contract with an implementation per service that carries mail."""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from email.message import EmailMessage

import aiosmtplib
from aiosmtplib.errors import SMTPRecipientRefused, SMTPRecipientsRefused

from config.base import EmailSettings
from enums.email import EmailProvider

# A mail server that accepts the connection and then says nothing would otherwise hold an item of the pass for whatever the library picked.
TIMEOUT = 15.0

logger = logging.getLogger(__name__)


class AddressRefused(Exception):
    """The server refused the recipient rather than the message, which is the only refusal that says nobody is there."""


@dataclass(frozen=True)
class Letter:
    """One message as every service that carries mail asks for it, which is the parts and never an envelope already sealed."""

    to: str
    subject: str
    html: str
    reply_to: str | None = None


class Mailer(ABC):
    """One service carries the mail of an environment, and the account it sends through is what the settings of that tenant declare."""

    @abstractmethod
    async def send(self, config: EmailSettings, letter: Letter) -> None: ...


class SmtpMailer(Mailer):
    """Anything that speaks SMTP, which is what a host, a port and a pair of credentials describe."""

    async def send(self, config: EmailSettings, letter: Letter) -> None:
        try:
            await aiosmtplib.send(self.envelope(config, letter), hostname=config.host, port=config.port, username=config.username or None, password=config.password or None, start_tls=config.use_tls, timeout=TIMEOUT)
        except (SMTPRecipientsRefused, SMTPRecipientRefused) as refusal:
            if self.refuses_the_address(refusal):
                raise AddressRefused(str(refusal)) from refusal

            raise

    def refuses_the_address(self, refusal: Exception) -> bool:
        """A 4xx is the server asking to be tried again, and only a 5xx about the recipient says there is nobody to try."""
        if isinstance(refusal, SMTPRecipientsRefused):
            return any(500 <= answer.code < 600 for answer in refusal.recipients)

        return 500 <= refusal.code < 600

    def envelope(self, config: EmailSettings, letter: Letter) -> EmailMessage:
        message = EmailMessage()
        message["From"] = f"{config.from_name} <{config.from_address}>"
        message["To"] = letter.to
        message["Subject"] = letter.subject

        if letter.reply_to:
            message["Reply-To"] = letter.reply_to

        message.set_content(letter.html, subtype="html")

        return message


class ConsoleMailer(Mailer):
    """What a machine with no mail server writes instead, so a recovery link is read off the log rather than waited for."""

    async def send(self, config: EmailSettings, letter: Letter) -> None:
        logger.info("[email] from=%s to=%s subject=%s\n%s", config.from_address, letter.to, letter.subject, letter.html)


PROVIDERS: dict[EmailProvider, Mailer] = {EmailProvider.SMTP: SmtpMailer(), EmailProvider.CONSOLE: ConsoleMailer()}


async def send(config: EmailSettings, letter: Letter) -> None:
    await PROVIDERS[config.provider].send(config, letter)
