"""An address proves it is the address before the account it opened answers, and whether it is asked to is one line of configuration."""

import pytest
from sqlalchemy import select

from enums.user import UserStatus
from helpers.settings import settings
from models.user import User
from services.email import email_service

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

    answered = await client.post(f"/api/account/confirmation/{posted[0]['token']}")

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

    assert (await client.post(f"/api/account/confirmation/{token}")).status_code == 200

    again = await client.post(f"/api/account/confirmation/{token}")

    assert again.status_code == 422
    assert again.json()["code"] == "error.confirmation-token-invalid"


async def test_a_token_nobody_was_sent_opens_nothing(client, tenant, tenant_headers):
    answered = await client.post("/api/account/confirmation/not-a-real-token")

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

    assert (await client.post(f"/api/account/confirmation/{first}")).status_code == 422
    assert (await client.post(f"/api/account/confirmation/{posted[1]['token']}")).status_code == 200


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
    await client.post(f"/api/account/confirmation/{posted[0]['token']}")

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
