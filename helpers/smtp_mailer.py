"""Anything that speaks SMTP, which is what a host, a port and a pair of credentials describe."""

import asyncio
import re
from email.message import EmailMessage
from email.utils import formataddr

import aiosmtplib
from aiosmtplib.errors import SMTPRecipientRefused, SMTPRecipientsRefused

from config.email_settings import EmailSettings
from helpers.address_refused import AddressRefused
from helpers.letter import Letter
from helpers.mailer_contract import Mailer

# A mail server that accepts the connection and then says nothing would otherwise hold an item of the pass for whatever the library picked.
TIMEOUT = 15.0


# The library waits that long for each reply, and one send waits on about ten of them, so a whole send has a ceiling of its own that the pass is sized against.
SEND_DEADLINE = 2 * TIMEOUT


# The enhanced status a server writes before its reason, as RFC 3463 numbers it: 5.1 is the address itself, and 5.2.1 a mailbox that was closed.
NOBODY_THERE = re.compile(r"^\s*5\.(?:1\.\d{1,3}|2\.1)(?!\.?\d)")


class SmtpMailer(Mailer):
    async def send(self, config: EmailSettings, letter: Letter) -> None:
        try:
            async with asyncio.timeout(SEND_DEADLINE):
                await aiosmtplib.send(self.envelope(config, letter), hostname=config.host, port=config.port, username=config.username or None, password=config.password or None, start_tls=config.use_tls, timeout=TIMEOUT)
        except (SMTPRecipientsRefused, SMTPRecipientRefused) as refusal:
            if self.refuses_the_address(refusal):
                raise AddressRefused(str(refusal)) from refusal

            raise

    def refuses_the_address(self, refusal: Exception) -> bool:
        """Only a refusal that names the address says there is nobody to try, while a relay, a policy or a refusal that says nothing about why is retried, because suppressing a reader over our own configuration would be silent and for good."""
        answers = refusal.recipients if isinstance(refusal, SMTPRecipientsRefused) else [refusal]

        return any(500 <= answer.code < 600 and NOBODY_THERE.match(answer.message) for answer in answers)

    def envelope(self, config: EmailSettings, letter: Letter) -> EmailMessage:
        message = EmailMessage()
        message["From"] = formataddr((letter.sender, config.from_address))
        message["To"] = letter.to
        message["Subject"] = letter.subject

        if letter.reply_to:
            message["Reply-To"] = letter.reply_to

        message.set_content(letter.html, subtype="html")

        return message
