"""How a written message leaves this process, which is one contract with an implementation per service that carries mail."""

from config.email_settings import EmailSettings
from enums.email_provider import EmailProvider
from helpers.console_mailer import ConsoleMailer
from helpers.letter import Letter
from helpers.mailer_contract import Mailer
from helpers.smtp_mailer import SmtpMailer

PROVIDERS: dict[EmailProvider, Mailer] = {EmailProvider.SMTP: SmtpMailer(), EmailProvider.CONSOLE: ConsoleMailer()}


async def send(config: EmailSettings, letter: Letter) -> None:
    await PROVIDERS[config.provider].send(config, letter)
