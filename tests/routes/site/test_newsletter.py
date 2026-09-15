"""Who hears from a brand is the address itself saying so, and never a form somebody else filled in."""

from datetime import timedelta

from sqlalchemy import func, select

from enums.newsletter import NewsletterStatus
from helpers.dates import now
from models.email import OutboundEmail
from models.newsletter import NewsletterSubscription
from services.newsletter import INVITATION_INTERVAL
from tests.conftest import opened, token_in


async def subscribed(site, email: str = "reader@acme.com"):
    token = await opened(site, "/newsletter")

    return await site.post("/newsletter", data={"csrf_token": token, "email": email}, follow_redirects=False)


async def test_the_page_draws_a_form_with_a_challenge(site):
    answer = await site.get("/newsletter")

    assert answer.status_code == 200
    assert 'name="email"' in answer.text


async def test_an_address_is_written_down_as_pending_and_asked_to_confirm(site, db, tenant):
    answer = await subscribed(site)

    assert answer.status_code == 303

    record = await db.scalar(select(NewsletterSubscription).where(NewsletterSubscription.email == "reader@acme.com"))
    queued = await db.scalar(select(OutboundEmail).where(OutboundEmail.to_address == "reader@acme.com"))

    assert record.status == NewsletterStatus.PENDING
    assert queued.template == "newsletter_confirm"
    assert record.token in queued.context["link"]


async def test_an_address_that_asks_twice_is_the_same_row(site, db):
    await subscribed(site)
    await subscribed(site)

    rows = (await db.execute(select(NewsletterSubscription).where(NewsletterSubscription.email == "reader@acme.com"))).scalars().all()

    assert len(rows) == 1


async def test_an_address_is_written_to_once_however_many_times_the_form_is_sent(site, db):
    """A form anybody can send was a way to mail somebody who never asked, one message per submit."""
    for _ in range(5):
        await subscribed(site)

    sent = await db.scalar(select(func.count()).select_from(OutboundEmail).where(OutboundEmail.to_address == "reader@acme.com"))

    assert sent == 1


async def test_an_invitation_is_offered_again_once_the_window_has_passed(site, db):
    """Somebody who never saw the first message asks again later, and the window is what tells that from a flood."""
    await subscribed(site)

    record = await db.scalar(select(NewsletterSubscription))
    record.invited_at = now() - INVITATION_INTERVAL - timedelta(minutes=1)
    await db.commit()

    await subscribed(site)

    sent = await db.scalar(select(func.count()).select_from(OutboundEmail).where(OutboundEmail.to_address == "reader@acme.com"))

    assert sent == 2


async def test_confirming_the_link_is_what_turns_a_subscription_on(site, db):
    await subscribed(site)

    record = await db.scalar(select(NewsletterSubscription))
    link = f"/newsletter/confirm/{record.token}"
    asked = await site.get(link)

    await db.refresh(record)

    # A scanner that opens the link on its own changes nothing, because only the answer sent from the page does.
    assert asked.status_code == 200
    assert record.status == NewsletterStatus.PENDING

    answer = await site.post(link, data={"csrf_token": token_in(asked.text)}, follow_redirects=False)

    await db.refresh(record)

    assert answer.status_code == 303
    assert record.status == NewsletterStatus.CONFIRMED
    assert record.settled_at is not None


async def test_a_confirmed_address_is_never_asked_to_confirm_again(site, db):
    await subscribed(site)

    record = await db.scalar(select(NewsletterSubscription))
    link = f"/newsletter/confirm/{record.token}"

    await site.post(link, data={"csrf_token": token_in((await site.get(link)).text)})
    await subscribed(site)

    queued = (await db.execute(select(OutboundEmail).where(OutboundEmail.template == "newsletter_confirm"))).scalars().all()

    assert len(queued) == 1


async def test_the_same_link_is_how_an_address_leaves(site, db):
    await subscribed(site)

    record = await db.scalar(select(NewsletterSubscription))
    link = f"/newsletter/unsubscribe/{record.token}"
    asked = await site.get(link)

    await db.refresh(record)

    assert record.status != NewsletterStatus.UNSUBSCRIBED

    await site.post(link, data={"csrf_token": token_in(asked.text)})
    await db.refresh(record)

    assert record.status == NewsletterStatus.UNSUBSCRIBED


async def test_a_token_that_names_nothing_is_not_a_page(site):
    assert (await site.get("/newsletter/confirm/nothing-here")).status_code == 404


async def test_an_address_the_rules_refuse_draws_the_form_again(site):
    answer = await subscribed(site, "not-an-address")

    assert answer.status_code == 422
    assert 'name="email"' in answer.text


async def test_the_link_that_goes_out_by_mail_points_at_the_site_the_brand_declares(app, db, tenant):
    """It is clicked in a mail client days later, so it cannot carry the host whoever filled the form happened to use."""
    from httpx import ASGITransport, AsyncClient

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://10.0.3.7") as stranger:
        await subscribed(stranger, "reader@acme.com")

    queued = await db.scalar(select(OutboundEmail).where(OutboundEmail.template == "newsletter_confirm"))
    record = await db.scalar(select(NewsletterSubscription).where(NewsletterSubscription.email == "reader@acme.com"))

    assert queued.context["link"] == f"http://{tenant.domain}/newsletter/confirm/{record.token}"
    assert "10.0.3.7" not in queued.context["link"]


async def test_a_letter_written_again_is_worded_in_one_language(db, tenant, monkeypatch):
    """The body is drawn in the language the address first asked in, and a subject in another would read as two letters glued together."""
    from helpers import brand
    from helpers.i18n import current_locale
    from services.email import email_service
    from services.newsletter import newsletter_subscription_service

    sent = []

    async def capture(db, tenant_id, to, subject, template, **context):
        sent.append((subject, context["locale"]))

    monkeypatch.setattr(email_service, "queue", capture)

    current_locale.set("pt")
    await newsletter_subscription_service.subscribe(db, brand.of(tenant), "leitor@acme.com", lambda token: f"/newsletter/confirm/{token}")

    record = await db.scalar(select(NewsletterSubscription))
    record.invited_at = now() - INVITATION_INTERVAL - timedelta(minutes=1)
    await db.commit()

    current_locale.set("en")
    await newsletter_subscription_service.subscribe(db, brand.of(tenant), "leitor@acme.com", lambda token: f"/newsletter/confirm/{token}")

    assert sent[1] == (sent[0][0], "pt")
