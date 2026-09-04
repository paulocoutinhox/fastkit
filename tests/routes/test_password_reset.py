"""The recovery token is the credential of a password reset, so it leaves by mail and never in an answer."""

import pytest
from sqlalchemy import select

from models.email import OutboundEmail
from models.user import User
from services.auth import auth_service
from services.email import email_service


@pytest.fixture
def posted(monkeypatch):
    sent = []

    original = email_service.queue

    async def capture(db, tenant_id, to, subject, template, **context):
        sent.append({"to": to, "subject": subject, "template": template, "tenant_id": tenant_id, **context})

        return await original(db, tenant_id, to, subject, template, **context)

    monkeypatch.setattr(email_service, "queue", capture)

    return sent


async def test_the_answer_never_carries_the_token(client, member, tenant, tenant_headers, posted):
    response = await client.post("/api/account/password-reset", headers=tenant_headers, json={"login": member.email})

    assert response.status_code == 204
    assert response.content == b""


async def test_a_login_nobody_has_answers_like_one_somebody_has(client, tenant_headers, member, posted):
    known = await client.post("/api/account/password-reset", headers=tenant_headers, json={"login": member.email})
    unknown = await client.post("/api/account/password-reset", headers=tenant_headers, json={"login": "ninguem@acme.com"})

    assert known.status_code == unknown.status_code
    assert known.content == unknown.content


async def test_the_token_goes_to_the_address_of_the_account(client, db, member, tenant, tenant_headers, posted):
    await client.post("/api/account/password-reset", headers=tenant_headers, json={"login": member.email})

    stored = await db.scalar(select(User.recovery_token).where(User.id == member.id))

    assert len(posted) == 1
    assert posted[0]["to"] == member.email
    assert posted[0]["token"] == stored
    assert posted[0]["template"] == "password_reset"
    assert posted[0]["tenant_id"] == tenant.id


async def test_a_login_nobody_has_sends_nothing(client, tenant_headers, posted):
    await client.post("/api/account/password-reset", headers=tenant_headers, json={"login": "ninguem@acme.com"})

    assert posted == []


async def test_a_mailer_that_is_down_keeps_the_message_and_is_written_down(client, db, member, tenant, tenant_headers, monkeypatch):
    """The queue is what makes a mailer that is down a delay and never a message nobody sent."""

    async def refuse(*args, **kwargs):
        raise ConnectionError("smtp is down")

    await client.post("/api/account/password-reset", headers=tenant_headers, json={"login": member.email})

    monkeypatch.setattr(email_service, "deliver_record", refuse)

    assert await email_service.process_pending(db) == []

    from models.email import OutboundEmail
    from models.system_log import SystemLog

    queued = await db.scalar(select(OutboundEmail))
    entries = (await db.execute(select(SystemLog).where(SystemLog.category == "account"))).scalars().all()

    assert queued.status == "pending"
    assert queued.attempts == 1
    assert "ConnectionError" in entries[0].description


async def test_confirming_a_reset_ends_every_session_the_old_password_opened(client, db, member, member_headers, tenant_headers, posted):
    await client.post("/api/account/password-reset", headers=tenant_headers, json={"login": member.email})

    token = await db.scalar(select(User.recovery_token).where(User.id == member.id))
    response = await client.post("/api/account/password-reset/confirm", json={"token": token, "newPassword": "uma-senha-nova"})

    assert response.status_code == 204
    assert (await client.get("/api/account/me", headers=member_headers)).status_code == 401


async def test_a_reset_leaves_the_account_findable_by_the_store(client, db, member, tenant_headers, posted):
    """The account token is the App User ID, and drawing it again would leave a paid subscription pointing at nobody."""
    before = member.token

    await client.post("/api/account/password-reset", headers=tenant_headers, json={"login": member.email})

    token = await db.scalar(select(User.recovery_token).where(User.id == member.id))
    await client.post("/api/account/password-reset/confirm", json={"token": token, "newPassword": "uma-senha-nova"})

    assert await db.scalar(select(User.token).where(User.id == member.id)) == before


async def test_changing_the_password_moves_the_account_past_every_session_it_opened(client, db, member, member_headers):
    before = member.session_epoch

    response = await client.post("/api/account/password", headers=member_headers, json={"currentPassword": "s3cret-password", "newPassword": "uma-senha-nova"})

    assert response.status_code == 200
    assert await db.scalar(select(User.session_epoch).where(User.id == member.id)) == before + 1


async def test_the_session_that_changed_the_password_is_handed_the_one_that_replaces_it(client, member_headers, member, db):
    """Whoever changed it stays in, and every other device is the one that has to sign in again."""
    changed = await client.post("/api/account/password", headers=member_headers, json={"currentPassword": "s3cret-password", "newPassword": "uma-senha-nova"})

    assert (await client.get("/api/account/me", headers=member_headers)).status_code == 401
    assert (await client.get("/api/account/me", headers={"Authorization": f"Bearer {changed.json()['token']}"})).status_code == 200


async def test_changing_the_password_leaves_the_account_findable_by_the_store(client, db, member, member_headers):
    before = member.token

    await client.post("/api/account/password", headers=member_headers, json={"currentPassword": "s3cret-password", "newPassword": "uma-senha-nova"})

    assert await db.scalar(select(User.token).where(User.id == member.id)) == before


async def test_an_account_with_no_address_is_not_mailed(client, db, member, tenant_headers, posted):
    member.email = None
    await db.commit()

    response = await client.post("/api/account/password-reset", headers=tenant_headers, json={"login": member.username})

    assert response.status_code == 204
    assert posted == []


async def test_a_reset_still_sets_the_password_it_was_asked_for(client, db, member, tenant, tenant_headers, posted):
    login = member.email
    tenant_id = tenant.id

    await client.post("/api/account/password-reset", headers=tenant_headers, json={"login": login})

    token = await db.scalar(select(User.recovery_token).where(User.id == member.id))
    await client.post("/api/account/password-reset/confirm", json={"token": token, "newPassword": "uma-senha-nova"})

    # The request committed on its own session, and this one still holds the row as it was read.
    db.expire_all()

    assert await auth_service.authenticate(db, tenant_id, login, "uma-senha-nova")


async def test_changing_the_password_burns_a_reset_that_was_still_pending(client, db, tenant, member, tenant_headers):
    """A token asked for by the old password is one more way in, and it used to survive the password that replaced it."""
    await client.post("/api/account/password-reset", json={"login": member.email}, headers=tenant_headers)
    await db.refresh(member)

    pending = member.recovery_token

    assert pending is not None

    token = (await client.post("/api/signin", json={"login": member.email, "password": "s3cret-password"}, headers=tenant_headers)).json()["token"]
    changed = await client.post("/api/account/password", json={"currentPassword": "s3cret-password", "newPassword": "another-password"}, headers={"Authorization": f"Bearer {token}"})

    assert changed.status_code == 200

    refused = await client.post("/api/account/password-reset/confirm", json={"token": pending, "newPassword": "taken-over-password"}, headers=tenant_headers)

    assert refused.status_code == 422
    assert refused.json()["code"] == "error.recovery-token-invalid"


async def test_the_message_carries_the_address_the_token_is_typed_into(client, db, member, tenant, tenant_headers):
    """The site takes the token in the path and nowhere else, so a code with no link is one nobody can use."""
    await client.post("/api/account/password-reset", json={"login": member.email}, headers=tenant_headers)

    queued = await db.scalar(select(OutboundEmail))
    await db.refresh(member)

    assert queued.context["link"] == f"http://{tenant.domain}/account/reset-password/{member.recovery_token}"


async def test_an_address_is_written_to_once_a_window_however_often_it_is_asked_for(client, db, member, tenant_headers):
    """The route is open and asks for no challenge, so asking again both fills a stranger's inbox and burns the token they are holding."""
    from datetime import timedelta

    from helpers.dates import now
    from helpers.settings import settings

    for _ in range(5):
        answer = await client.post("/api/account/password-reset", json={"login": member.email}, headers=tenant_headers)

        assert answer.status_code == 204, "the answer never says whether anything was sent"

    queued = (await db.execute(select(OutboundEmail).where(OutboundEmail.template == "password_reset"))).scalars().all()

    assert len(queued) == 1

    await db.refresh(member)
    held = member.recovery_token

    # Past the window the address may ask again, and the token it is given is a new one.
    member.recovery_token_created_at = now() - timedelta(seconds=settings.password_reset_interval + 1)
    await db.commit()

    assert (await client.post("/api/account/password-reset", json={"login": member.email}, headers=tenant_headers)).status_code == 204

    await db.refresh(member)

    assert member.recovery_token != held
    assert len((await db.execute(select(OutboundEmail).where(OutboundEmail.template == "password_reset"))).scalars().all()) == 2
