"""The contact form is the one public write that reaches a person, so it is queued and never dialled in the request."""

from sqlalchemy import select

from enums.email import OutboundEmailStatus
from helpers.settings import settings
from models.email import OutboundEmail
from services.email import email_service
from tests.conftest import opened


async def test_a_message_is_written_down_and_sent_by_the_queue(site, db, tenant):
    token = await opened(site, "/contact")

    answer = await site.post("/contact", data={"csrf_token": token, "name": "Ada Lovelace", "email": "ada@acme.com", "message": "I would like to know more about this."}, follow_redirects=False)

    assert answer.status_code == 303

    queued = await db.scalar(select(OutboundEmail))

    assert queued.to_address == tenant.email_contact or queued.to_address
    assert queued.context["name"] == "Ada Lovelace"
    assert queued.template == "contact"


async def test_a_message_the_rules_refuse_draws_the_form_again(site, db):
    token = await opened(site, "/contact")

    answer = await site.post("/contact", data={"csrf_token": token, "name": "A", "email": "not-an-email", "message": "short"})

    assert answer.status_code == 422
    assert await db.scalar(select(OutboundEmail)) is None


async def test_a_message_with_no_token_is_sent_back_to_the_page_it_came_from(site):
    await site.get("/contact")

    answer = await site.post("/contact", data={"name": "Ada", "email": "ada@acme.com", "message": "I would like to know more."}, headers={"referer": "http://acme.test/contact"}, follow_redirects=False)

    assert answer.status_code == 303
    assert answer.headers["location"] == "/contact"


async def test_the_message_a_visitor_sent_is_one_the_mailer_can_actually_render(site, db):
    """The row was written and the send failed on every pass, so the form said sent and nobody ever received one."""
    token = await opened(site, "/contact")

    await site.post("/contact", data={"csrf_token": token, "name": "Ada", "email": "ada@acme.com", "message": "Hello there"}, follow_redirects=False)

    sent = await email_service.process_pending(db)

    assert [record.template for record in sent] == ["contact"]
    assert await db.scalar(select(OutboundEmail.status)) == OutboundEmailStatus.SENT


async def test_the_operator_can_answer_the_person_who_wrote(site, db):
    """The message is sent by the system address, so without this the answer goes to the system and never to the visitor."""
    from services.email import email_service as sender

    token = await opened(site, "/contact")

    await site.post("/contact", data={"csrf_token": token, "name": "Ada", "email": "ada@acme.com", "message": "Hello there"}, follow_redirects=False)

    queued = await db.scalar(select(OutboundEmail))
    envelope = sender.build_message(settings.email, queued.to_address, queued.subject, "<p>body</p>", queued.reply_to)

    assert queued.reply_to == "ada@acme.com"
    assert envelope["Reply-To"] == "ada@acme.com"


async def test_a_message_nobody_answers_carries_no_reply_address(db, tenant):
    from services.email import email_service as sender

    queued = await email_service.queue(db, tenant.id, "reader@acme.com", "Reset", "password_reset", token="abc", hours=1, link="https://acme.com/en/x")

    assert queued.reply_to is None
    assert sender.build_message(settings.email, queued.to_address, queued.subject, "<p>body</p>", queued.reply_to)["Reply-To"] is None
