import logging
from datetime import timedelta
from email.message import EmailMessage as Envelope

import aiosmtplib
from aiosmtplib.errors import SMTPRecipientRefused, SMTPRecipientsRefused
from sqlalchemy import select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from config.base import EmailSettings
from enums.email import OutboundEmailStatus
from enums.system_log import LogCategory, LogLevel
from helpers.dates import now
from helpers.db import insert_or_read
from helpers.i18n import current_locale, translate
from helpers.settings import settings
from helpers.templates import render
from models.email import OutboundEmail, SuppressedAddress
from models.language import Language
from models.user import User
from services.crud import CrudService
from services.system_log import system_log_service
from services.tenant import tenant_service

# A message that keeps failing stops being retried, or it would hold a slot of every pass forever.
MAX_ATTEMPTS = 5

# A send takes seconds, so a row still claimed after this belonged to a process that is gone.
ABANDONED_AFTER = timedelta(minutes=30)

logger = logging.getLogger(__name__)


def refused_for_good(error: Exception) -> bool:
    """Whether the server refused this address rather than this message, which is the only refusal that says nobody is there."""
    if isinstance(error, SMTPRecipientsRefused):
        return any(500 <= refusal.code < 600 for refusal in error.recipients)

    return isinstance(error, SMTPRecipientRefused) and 500 <= error.code < 600


class OutboundEmailService(CrudService):
    """The queue an operator reads when somebody says the message never arrived."""

    model = OutboundEmail
    search_fields = ("to_address", "template")
    filter_fields = ("tenant_id", "status", "template")
    ordering_fields = ("id", "status", "attempts", "sent_at", "created_at")
    default_ordering = "-id"
    relations = ("tenant",)
    label_fields = ("subject",)


class EmailService:
    """A message is written down first and dialled out later, so a mailer that is down delays it and never loses it."""

    async def queue(self, db: AsyncSession, tenant_id: int | None, to: str, subject: str, template: str, reply_to: str | None = None, locale: str | None = None, **context) -> OutboundEmail:
        record = OutboundEmail(tenant_id=tenant_id, to_address=to, subject=subject, template=template, locale=locale or current_locale.get(), reply_to=reply_to, context=context)

        # An address a server already refused is written down as refused rather than dialled, because nobody is there to read it.
        if await self.suppressed(db, to):
            record.status = OutboundEmailStatus.REFUSED
            record.error_code = "SuppressedAddress"

        db.add(record)
        await db.commit()

        return record

    async def suppressed(self, db: AsyncSession, address: str) -> bool:
        return await db.scalar(select(SuppressedAddress.id).where(SuppressedAddress.address == address)) is not None

    async def suppress(self, db: AsyncSession, address: str, reason: str) -> None:
        await insert_or_read(db, SuppressedAddress(address=address, reason=reason[:255]), select(SuppressedAddress).where(SuppressedAddress.address == address))

    async def to_user(self, db: AsyncSession, tenant_id: int | None, user: User, subject_key: str, template: str, **context) -> OutboundEmail:
        """A message to an account is written in the language of that account, which is not the language of whoever set it off."""
        locale = await self.language_of(db, user)

        return await self.queue(db, tenant_id, user.email, translate(subject_key, locale), template, locale=locale, **context)

    async def language_of(self, db: AsyncSession, user: User) -> str:
        """What the account chose, falling back to the language of the request for an account that never chose one."""
        code = await db.scalar(select(Language.code_iso_639_1).where(Language.id == user.language_id)) if user.language_id else None

        return code if code in settings.languages else current_locale.get()

    async def process_pending(self, db: AsyncSession, limit: int = 50) -> list[OutboundEmail]:
        statement = select(OutboundEmail.id).where(OutboundEmail.status == OutboundEmailStatus.PENDING, OutboundEmail.attempts < MAX_ATTEMPTS).order_by(OutboundEmail.created_at.asc()).limit(limit)
        sent = []

        for record_id in (await db.execute(statement)).scalars():
            if not await self.claim(db, record_id):
                continue

            settled = await self.settle(db, record_id)

            if settled is not None:
                sent.append(settled)

        return sent

    async def settle(self, db: AsyncSession, record_id: int) -> OutboundEmail | None:
        """One message, dialled once and written down after, where nothing that happens to it takes the rest of the pass with it."""
        record = await db.get(OutboundEmail, record_id)

        try:
            await self.deliver_record(db, record)
        except Exception as error:
            await self.write_down(db, record_id, error)

            return None

        return await self.write_down(db, record_id, None)

    async def write_down(self, db: AsyncSession, record_id: int, error: Exception | None) -> OutboundEmail | None:
        """How the message ended, written on the row that was claimed for it."""
        record = await db.get(OutboundEmail, record_id)

        try:
            if error is not None:
                await self.fail(db, record, error)
                await db.commit()

                return None

            record.status = OutboundEmailStatus.SENT
            record.sent_at = now()
            record.error_code = None
            record.error_message = None
            await db.commit()

            return record
        except SQLAlchemyError:
            # It was dialled and the row never said so, and what brings it back is the reclaim its claim runs out into.
            logger.exception("[email] %s was dialled and could not be written down, and the reclaim is what brings it back", record_id)
            await db.rollback()

            return None

    async def claim(self, db: AsyncSession, record_id: int) -> bool:
        """Takes a message for this caller to send, and answers whether it was the one that got it: two nodes with the same tag would otherwise dial it twice."""
        statement = update(OutboundEmail).where(OutboundEmail.id == record_id, OutboundEmail.status == OutboundEmailStatus.PENDING).values(status=OutboundEmailStatus.SENDING, attempts=OutboundEmail.attempts + 1)
        claimed = (await db.execute(statement)).rowcount == 1

        await db.commit()

        return claimed

    async def reclaim_abandoned(self, db: AsyncSession) -> int:
        """What a node that died mid-send left claimed, handed back to the queue — one write over the whole table, so only the job runs it."""
        abandoned = update(OutboundEmail).where(OutboundEmail.status == OutboundEmailStatus.SENDING, OutboundEmail.updated_at < now() - ABANDONED_AFTER).values(status=OutboundEmailStatus.PENDING)
        reclaimed = (await db.execute(abandoned)).rowcount

        await db.commit()

        return reclaimed

    async def fail(self, db: AsyncSession, record: OutboundEmail, error: Exception) -> None:
        """A template nobody wrote is a configuration to fix, and the server answers the request either way."""
        if refused_for_good(error):
            record.status = OutboundEmailStatus.REFUSED
            record.error_code = type(error).__name__
            record.error_message = str(error)

            await self.suppress(db, record.to_address, str(error))
            await system_log_service.record(db, record.tenant_id, None, LogLevel.WARNING, LogCategory.ACCOUNT, f"{record.to_address} was refused for good and stops receiving", {"outbound_email_id": record.id, "error": str(error)})

            return

        record.status = OutboundEmailStatus.FAILED if record.attempts >= MAX_ATTEMPTS else OutboundEmailStatus.PENDING
        record.error_code = type(error).__name__
        record.error_message = str(error)

        await system_log_service.record(db, record.tenant_id, None, LogLevel.ERROR, LogCategory.ACCOUNT, f"email {record.template} to {record.to_address} failed: {type(error).__name__}", {"outbound_email_id": record.id, "error": str(error)})

    async def deliver_record(self, db: AsyncSession, record: OutboundEmail) -> None:
        code = await tenant_service.code_of(db, record.tenant_id)
        config = settings.email_for(code)

        token = current_locale.set(record.locale)

        try:
            body = render(f"email/{record.template}.html", code, {"brand": config.from_name, "subject": record.subject, **record.context})
        finally:
            current_locale.reset(token)

        message = self.build_message(config, record.to_address, record.subject, body, record.reply_to)

        if config.provider == "console":
            logger.info("[email] to=%s subject=%s\n%s", record.to_address, record.subject, body)

            return

        await self.deliver(config, message)

    def build_message(self, config: EmailSettings, to: str, subject: str, body: str, reply_to: str | None = None) -> Envelope:
        message = Envelope()
        message["From"] = f"{config.from_name} <{config.from_address}>"
        message["To"] = to
        message["Subject"] = subject

        if reply_to:
            message["Reply-To"] = reply_to

        message.set_content(body, subtype="html")

        return message

    async def deliver(self, config: EmailSettings, message: Envelope) -> None:
        await aiosmtplib.send(message, hostname=config.host, port=config.port, username=config.username or None, password=config.password or None, start_tls=config.use_tls)


outbound_email_service = OutboundEmailService()
email_service = EmailService()
