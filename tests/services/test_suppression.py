"""An address a server refused for good stops receiving, because writing to the dead burns the reputation of the domain."""

import pytest
from aiosmtplib.errors import SMTPAuthenticationError, SMTPRecipientRefused, SMTPRecipientsRefused, SMTPResponseException
from sqlalchemy import func, select

from config.base import EmailSettings
from enums.email import EmailProvider, OutboundEmailStatus
from helpers import mailer
from models.email import OutboundEmail, SuppressedAddress
from services.email import email_service

GONE = SMTPRecipientsRefused([SMTPRecipientRefused(550, "No such user here", "gone@acme.com")])
BUSY = SMTPRecipientsRefused([SMTPRecipientRefused(450, "Mailbox busy", "busy@acme.com")])

SENDING = EmailSettings(provider=EmailProvider.SMTP, host="smtp.acme.com", port=2525, from_name="Acme", from_address="no-reply@acme.com")


def dialling(monkeypatch, refusal):
    async def refuse(*args, **kwargs):
        raise refusal

    monkeypatch.setattr(mailer.aiosmtplib, "send", refuse)


@pytest.mark.parametrize("refusal, dead", [(GONE, True), (SMTPRecipientRefused(550, "No such user here", "gone@acme.com"), True), (BUSY, False), (SMTPResponseException(550, "Message rejected"), False), (SMTPAuthenticationError(535, "Bad credentials"), False), (RuntimeError("something else"), False)])
async def test_only_a_refusal_of_the_address_says_nobody_is_there(refusal, dead, monkeypatch):
    """Our own credentials being wrong is a 5xx too, and suppressing a real reader for that would be silent."""
    dialling(monkeypatch, refusal)

    with pytest.raises(mailer.AddressRefused if dead else type(refusal)):
        await mailer.PROVIDERS[EmailProvider.SMTP].send(SENDING, mailer.Letter(to="gone@acme.com", subject="Hello", html="<p>hi</p>"))


async def test_what_the_queue_reads_is_the_refusal_and_never_the_shape_of_one_vendor(db, tenant, monkeypatch):
    """The service asks whether the address was refused, and which exception a service that carries mail raises is the business of its provider."""
    record = await email_service.queue(db, tenant.id, "gone@acme.com", "Hello", "contact", name="A", email="a@acme.com", message="b")

    async def refuse(config, letter):
        raise mailer.AddressRefused("550 No such user here")

    monkeypatch.setattr(mailer, "send", refuse)

    await email_service.claim(db, record.id)
    await email_service.settle(db, record.id)
    await db.refresh(record)

    assert record.status == OutboundEmailStatus.REFUSED
    assert await email_service.suppressed(db, "gone@acme.com") is True


async def test_an_address_refused_for_good_stops_being_dialled(db, tenant, monkeypatch):
    record = await email_service.queue(db, tenant.id, "gone@acme.com", "Hello", "contact", name="A", email="a@acme.com", message="b")

    dialling(monkeypatch, GONE)
    monkeypatch.setattr("helpers.settings.settings.email.provider", EmailProvider.SMTP)

    await email_service.claim(db, record.id)
    await email_service.settle(db, record.id)
    await db.refresh(record)

    assert record.status == OutboundEmailStatus.REFUSED
    assert await email_service.suppressed(db, "gone@acme.com") is True


async def test_a_busy_mailbox_is_tried_again(db, tenant, monkeypatch):
    record = await email_service.queue(db, tenant.id, "busy@acme.com", "Hello", "contact", name="A", email="a@acme.com", message="b")

    dialling(monkeypatch, BUSY)
    monkeypatch.setattr("helpers.settings.settings.email.provider", EmailProvider.SMTP)

    await email_service.claim(db, record.id)
    await email_service.settle(db, record.id)
    await db.refresh(record)

    assert record.status == OutboundEmailStatus.PENDING
    assert await email_service.suppressed(db, "busy@acme.com") is False


async def test_nothing_is_written_to_an_address_that_was_refused(db, tenant):
    await email_service.suppress(db, "gone@acme.com", "550 No such user here")
    await db.commit()

    record = await email_service.queue(db, tenant.id, "gone@acme.com", "Hello", "contact", name="A", email="a@acme.com", message="b")

    assert record.status == OutboundEmailStatus.REFUSED
    assert record.error_code == "SuppressedAddress"


async def test_a_refusal_written_twice_is_one_address(db):
    await email_service.suppress(db, "gone@acme.com", "550 first")
    await email_service.suppress(db, "gone@acme.com", "550 second")
    await db.commit()

    assert await db.scalar(select(func.count()).select_from(SuppressedAddress)) == 1


async def test_an_address_nobody_refused_is_dialled_as_it_always_was(db, tenant):
    record = await email_service.queue(db, tenant.id, "alive@acme.com", "Hello", "contact", name="A", email="a@acme.com", message="b")

    assert record.status == OutboundEmailStatus.PENDING
    assert await db.scalar(select(func.count()).select_from(OutboundEmail).where(OutboundEmail.status == OutboundEmailStatus.PENDING)) == 1
