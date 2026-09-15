"""Who hears from a brand is the address itself saying so, and never a form somebody else filled in."""

from datetime import timedelta

from sqlalchemy import func, select

from enums.newsletter import NewsletterStatus
from helpers.dates import now
from models.email import OutboundEmail
from models.newsletter import NewsletterSubscription
from services.newsletter import INVITATION_INTERVAL
from tests.conftest import opened


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
    answer = await site.get(f"/newsletter/confirm/{record.token}", follow_redirects=False)

    await db.refresh(record)

    assert answer.status_code == 303
    assert record.status == NewsletterStatus.CONFIRMED
    assert record.settled_at is not None


async def test_a_confirmed_address_is_never_asked_to_confirm_again(site, db):
    await subscribed(site)

    record = await db.scalar(select(NewsletterSubscription))
    await site.get(f"/newsletter/confirm/{record.token}")

    await subscribed(site)

    queued = (await db.execute(select(OutboundEmail).where(OutboundEmail.template == "newsletter_confirm"))).scalars().all()

    assert len(queued) == 1


async def test_the_same_link_is_how_an_address_leaves(site, db):
    await subscribed(site)

    record = await db.scalar(select(NewsletterSubscription))
    await site.get(f"/newsletter/unsubscribe/{record.token}")

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
