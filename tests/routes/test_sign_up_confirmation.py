"""An address proves it is the address before the account it opened answers, and whether it is asked to is one line of configuration."""

import pytest
from sqlalchemy import select

from enums.user import UserStatus
from helpers.errors import ValidationError
from helpers.settings import settings
from models.user import User
from services.auth import auth_service
from services.email import email_service
from services.user import user_service

SIGNING_UP = {"email": "ada@acme.com", "password": "a-strong-secret", "firstName": "Ada"}


@pytest.fixture
def posted(monkeypatch):
    sent = []

    original = email_service.queue

    async def capture(db, tenant_id, to, subject, template, **context):
        sent.append({"to": to, "template": template, **context})

        return await original(db, tenant_id, to, subject, template, **context)

    monkeypatch.setattr(email_service, "queue", capture)

    return sent


async def waiting(db, email: str) -> User:
    return await db.scalar(select(User).where(User.email == email))


async def test_signing_up_answers_no_session_and_writes_to_the_address(client, db, tenant, tenant_headers, posted):
    answer = await client.post("/api/signup", headers=tenant_headers, json=SIGNING_UP)

    assert answer.status_code == 201
    assert answer.json()["token"] is None
    assert answer.json()["user"]["status"] == UserStatus.PENDING

    assert [message["to"] for message in posted] == ["ada@acme.com"]
    assert posted[0]["template"] == "account_confirmation"


async def test_the_account_it_opened_cannot_sign_in_until_the_address_answers(client, tenant, tenant_headers):
    await client.post("/api/signup", headers=tenant_headers, json=SIGNING_UP)

    refused = await client.post("/api/signin", headers=tenant_headers, json={"login": "ada@acme.com", "password": "a-strong-secret"})

    assert refused.status_code == 401
    assert refused.json()["code"] == "error.account-pending"


async def test_answering_the_link_opens_the_account_and_hands_over_a_session(client, db, tenant, tenant_headers, posted):
    await client.post("/api/signup", headers=tenant_headers, json=SIGNING_UP)

    answered = await client.post(f"/api/account/confirmation/{posted[0]['token']}", headers=tenant_headers)

    assert answered.status_code == 200
    assert answered.json()["token"]
    assert answered.json()["user"]["status"] == UserStatus.ACTIVE

    account = await waiting(db, "ada@acme.com")
    await db.refresh(account)

    # The token goes with the status, or the same link would keep opening an account that is already open.
    assert account.confirmation_token is None


async def test_the_same_link_never_opens_the_account_twice(client, tenant, tenant_headers, posted):
    await client.post("/api/signup", headers=tenant_headers, json=SIGNING_UP)

    token = posted[0]["token"]

    assert (await client.post(f"/api/account/confirmation/{token}", headers=tenant_headers)).status_code == 200

    again = await client.post(f"/api/account/confirmation/{token}", headers=tenant_headers)

    assert again.status_code == 422
    assert again.json()["code"] == "error.confirmation-token-invalid"


async def test_a_token_nobody_was_sent_opens_nothing(client, tenant, tenant_headers):
    answered = await client.post("/api/account/confirmation/not-a-real-token", headers=tenant_headers)

    assert answered.status_code == 422
    assert answered.json()["code"] == "error.confirmation-token-invalid"


async def test_asking_again_writes_a_new_letter_and_retires_the_one_before_it(client, db, tenant, tenant_headers, posted, monkeypatch):
    """Only the last letter sent to an address opens the account, so a mailbox holding two of them still holds one that works."""
    monkeypatch.setattr(settings, "confirm_sign_up_interval", 0)

    await client.post("/api/signup", headers=tenant_headers, json=SIGNING_UP)

    first = posted[0]["token"]
    again = await client.post("/api/account/confirmation", headers=tenant_headers, json={"login": "ada@acme.com"})

    assert again.status_code == 204
    assert len(posted) == 2
    assert posted[1]["token"] != first

    assert (await client.post(f"/api/account/confirmation/{first}", headers=tenant_headers)).status_code == 422
    assert (await client.post(f"/api/account/confirmation/{posted[1]['token']}", headers=tenant_headers)).status_code == 200


async def test_an_address_is_written_to_once_a_window_however_often_it_is_asked(client, tenant, tenant_headers, posted):
    """The route is open and asks for no challenge, so without the window a form would write to a stranger's inbox as fast as it could post."""
    await client.post("/api/signup", headers=tenant_headers, json=SIGNING_UP)

    for _ in range(5):
        assert (await client.post("/api/account/confirmation", headers=tenant_headers, json={"login": "ada@acme.com"})).status_code == 204

    assert len(posted) == 1


@pytest.mark.parametrize("login", ["nobody@acme.com", "ada@acme.com"])
async def test_asking_for_an_account_that_is_not_waiting_answers_exactly_like_one_that_is(client, tenant, tenant_headers, posted, login):
    """An open route that answered differently would be a way of asking who has an account here, and who has confirmed one."""
    await client.post("/api/signup", headers=tenant_headers, json=SIGNING_UP)
    await client.post(f"/api/account/confirmation/{posted[0]['token']}", headers=tenant_headers)

    posted.clear()

    answer = await client.post("/api/account/confirmation", headers=tenant_headers, json={"login": login})

    assert answer.status_code == 204
    assert posted == []


async def test_where_the_environment_asks_for_no_confirmation_the_account_is_open_at_once(client, db, tenant, tenant_headers, posted, monkeypatch):
    monkeypatch.setattr(settings, "confirm_sign_up", False)

    answer = await client.post("/api/signup", headers=tenant_headers, json=SIGNING_UP)

    assert answer.status_code == 201
    assert answer.json()["token"]
    assert answer.json()["user"]["status"] == UserStatus.ACTIVE
    assert posted == []


async def test_an_account_with_no_address_has_nothing_to_prove(client, db, tenant, tenant_headers, posted):
    """An account is created with any one of four identities, so one that named no address has nowhere to be written to."""
    answer = await client.post("/api/signup", headers=tenant_headers, json={"username": "ada", "password": "a-strong-secret"})

    assert answer.status_code == 201
    assert answer.json()["token"]
    assert answer.json()["user"]["status"] == UserStatus.ACTIVE
    assert posted == []


async def test_a_letter_a_newer_one_replaced_opens_nothing_even_mid_race(db, tenant, monkeypatch):
    """Asking for the letter again draws a new token while the old link may already be on its way in, and only the last letter opens the account."""
    user = await user_service.create(db, {"email": "late@acme.com", "password": "s3cret-password", "tenant_id": tenant.id, "status": UserStatus.PENDING})
    user.confirmation_token = "the-newer-one"
    await db.commit()

    async def read_before_the_new_letter(session, tenant_id, token):
        return user

    monkeypatch.setattr(auth_service, "awaiting_confirmation", read_before_the_new_letter)

    with pytest.raises(ValidationError):
        await auth_service.confirm_sign_up(db, tenant.id, "the-older-one")

    await db.refresh(user)

    assert user.status == UserStatus.PENDING


async def test_a_new_address_waits_for_its_letter_before_it_replaces_the_one_the_account_proved(client, db, member, member_headers, tenant_headers, posted):
    """Writing an address is not proving it, so an account that signed up without one, or changes the one it has, is asked the same thing the sign up asks."""
    answer = await client.put("/api/account/me", json={"email": "new@acme.com"}, headers=member_headers)
    held = await db.scalar(select(User).where(User.id == member.id).execution_options(populate_existing=True))

    assert answer.status_code == 200
    assert answer.json()["email"] == "reader@acme.com"
    assert answer.json()["pendingEmail"] == "new@acme.com"
    assert [(letter["to"], letter["template"]) for letter in posted] == [("new@acme.com", "address_confirmation")]

    confirmed = await client.post(f"/api/account/confirmation/{held.confirmation_token}", headers=tenant_headers)
    settled = await db.scalar(select(User).where(User.id == member.id).execution_options(populate_existing=True))

    assert confirmed.status_code == 200
    # The letter proves the mailbox and not the account, so answering it writes the address and starts no session.
    assert confirmed.json()["token"] is None
    assert (settled.email, settled.pending_email, settled.status) == ("new@acme.com", None, UserStatus.ACTIVE)


async def test_an_address_another_account_holds_is_refused_before_any_letter_is_written(client, db, tenant, member, member_headers, posted):
    await user_service.create(db, {"email": "taken@acme.com", "password": "a-strong-secret", "tenant_id": tenant.id})

    answer = await client.put("/api/account/me", json={"email": "taken@acme.com"}, headers=member_headers)

    assert answer.status_code == 409
    assert answer.json()["code"] == "error.email-already-used"
    assert posted == []


async def test_an_address_somebody_else_proved_first_is_refused_when_the_letter_is_answered(client, db, tenant, member, member_headers, tenant_headers, posted):
    """Two accounts may both wait on one address, and the one that answers second meets the index instead of a second owner."""
    await client.put("/api/account/me", json={"email": "contested@acme.com"}, headers=member_headers)
    token = await db.scalar(select(User.confirmation_token).where(User.id == member.id))
    await user_service.create(db, {"email": "contested@acme.com", "password": "a-strong-secret", "tenant_id": tenant.id})

    answer = await client.post(f"/api/account/confirmation/{token}", headers=tenant_headers)

    assert answer.status_code == 409
    assert await db.scalar(select(User.email).where(User.id == member.id).execution_options(populate_existing=True)) == "reader@acme.com"


async def test_an_operator_writing_the_address_writes_it_and_forgets_the_one_waiting(client, db, member, member_headers, admin_headers, posted):
    await client.put("/api/account/me", json={"email": "new@acme.com"}, headers=member_headers)

    answer = await client.put(f"/api/users/{member.id}", json={"email": "set@acme.com"}, headers=admin_headers)
    settled = await db.scalar(select(User).where(User.id == member.id).execution_options(populate_existing=True))

    assert answer.status_code == 200
    assert (settled.email, settled.pending_email) == ("set@acme.com", None)


async def test_saving_the_form_again_keeps_the_address_waiting_and_its_letter_opening(client, db, member, member_headers, admin_headers, tenant_headers, posted):
    """Every form sends back the address it was filled with, which is the current one, so a second save of anything else is not an answer to the first."""
    await client.put("/api/account/me", json={"email": "new@acme.com"}, headers=member_headers)
    token = await db.scalar(select(User.confirmation_token).where(User.id == member.id))

    await client.put("/api/account/me", json={"email": "reader@acme.com", "nickname": "Reader"}, headers=member_headers)
    await client.put("/api/account/me", json={"email": "new@acme.com", "timezone": "America/Sao_Paulo"}, headers=member_headers)
    await client.put(f"/api/users/{member.id}", json={"email": "reader@acme.com", "nickname": "Kept"}, headers=admin_headers)

    assert [letter["to"] for letter in posted] == ["new@acme.com"]
    assert (await client.post(f"/api/account/confirmation/{token}", headers=tenant_headers)).status_code == 200
    assert await db.scalar(select(User.email).where(User.id == member.id).execution_options(populate_existing=True)) == "new@acme.com"


async def test_a_letter_written_for_one_address_never_proves_the_next_one(client, db, member, member_headers, tenant_headers, posted):
    """Inside the window the second address gets no letter, and the one already out must not open it, or anyone takes an address by answering their own."""
    await client.put("/api/account/me", json={"email": "own@acme.com"}, headers=member_headers)
    token = await db.scalar(select(User.confirmation_token).where(User.id == member.id))

    await client.put("/api/account/me", json={"email": "victim@acme.com"}, headers=member_headers)

    assert (await client.post(f"/api/account/confirmation/{token}", headers=tenant_headers)).status_code == 422
    assert await db.scalar(select(User.email).where(User.id == member.id).execution_options(populate_existing=True)) == "reader@acme.com"


async def test_with_the_rule_off_an_account_writes_its_address_at_once(client, db, member, member_headers, posted, monkeypatch):
    monkeypatch.setattr(settings, "confirm_sign_up", False)

    answer = await client.put("/api/account/me", json={"email": "new@acme.com"}, headers=member_headers)

    assert answer.json()["email"] == "new@acme.com"
    assert posted == []
