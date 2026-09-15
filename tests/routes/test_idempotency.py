"""A write a client named, because an application that retries a checkout must not open a second payment."""

from datetime import timedelta

import pytest
from sqlalchemy import func, select

from helpers import idempotency
from helpers.dates import now
from helpers.errors import ConflictError
from helpers.idempotency import HEADER
from models.idempotency import ClientRequest
from services.checkout import checkout_service
from tests.factories import make_product

BODY = {"successUrl": "https://acme.com/ok", "cancelUrl": "https://acme.com/no"}


@pytest.fixture(autouse=True)
def gateway(monkeypatch):
    opened = []

    async def answer(session, tenant, user, product, success_url, cancel_url):
        opened.append(product.id)

        return f"https://gateway.acme.com/{len(opened)}"

    monkeypatch.setattr(checkout_service, "for_product", answer)

    return opened


async def test_the_same_key_answers_the_same_thing_and_pays_once(client, db, tenant, member_headers, tenant_headers, gateway):
    product = await make_product(db, tenant)
    headers = member_headers | tenant_headers | {HEADER: "abc-123"}

    first = await client.post(f"/api/commerce/products/{product.slug}/checkout", json=BODY, headers=headers)
    second = await client.post(f"/api/commerce/products/{product.slug}/checkout", json=BODY, headers=headers)

    assert first.json()["url"] == second.json()["url"]
    assert gateway == [product.id]


async def test_a_call_that_names_nothing_is_answered_every_time(client, db, tenant, member_headers, tenant_headers, gateway):
    """Naming a write is what a client asks for, so one that names none behaves exactly as it always did."""
    product = await make_product(db, tenant)
    headers = member_headers | tenant_headers

    await client.post(f"/api/commerce/products/{product.slug}/checkout", json=BODY, headers=headers)
    await client.post(f"/api/commerce/products/{product.slug}/checkout", json=BODY, headers=headers)

    assert len(gateway) == 2


async def test_a_name_whose_write_failed_is_given_back_for_the_retry_it_exists_for(client, db, tenant, member_headers, tenant_headers, monkeypatch):
    """A refused checkout opened nothing the name could answer for, so the retry runs instead of waiting out the window as if a call were still working."""
    from helpers.errors import AppError

    product = await make_product(db, tenant)
    headers = member_headers | tenant_headers | {HEADER: "retry-me"}
    calls = []

    async def refused_once(session, brand, user, product, success_url, cancel_url):
        calls.append(product.id)

        if len(calls) == 1:
            raise AppError("error.checkout-refused")

        return "https://gateway.acme.com/second"

    monkeypatch.setattr(checkout_service, "for_product", refused_once)

    first = await client.post(f"/api/commerce/products/{product.slug}/checkout", json=BODY, headers=headers)
    second = await client.post(f"/api/commerce/products/{product.slug}/checkout", json=BODY, headers=headers)

    assert first.json()["code"] == "error.checkout-refused"
    assert second.json()["url"] == "https://gateway.acme.com/second"
    assert await db.scalar(select(func.count()).select_from(ClientRequest)) == 1


async def test_two_names_are_two_payments(client, db, tenant, member_headers, tenant_headers, gateway):
    product = await make_product(db, tenant)
    headers = member_headers | tenant_headers

    await client.post(f"/api/commerce/products/{product.slug}/checkout", json=BODY, headers=headers | {HEADER: "one"})
    await client.post(f"/api/commerce/products/{product.slug}/checkout", json=BODY, headers=headers | {HEADER: "two"})

    assert len(gateway) == 2


async def test_a_name_still_being_answered_is_refused(client, db, tenant, member, member_headers, tenant_headers, gateway):
    """Two calls arriving together would both look first and both pay, so the key is taken before the work starts."""
    product = await make_product(db, tenant)
    db.add(ClientRequest(user_id=member.id, idempotency_key="in-flight", endpoint="commerce-product-checkout"))
    await db.commit()

    answer = await client.post(f"/api/commerce/products/{product.slug}/checkout", json=BODY, headers=member_headers | tenant_headers | {HEADER: "in-flight"})

    assert answer.status_code == 409
    assert answer.json()["code"] == "error.idempotency-key-in-flight"
    assert gateway == []


async def test_a_name_whose_call_never_finished_stops_holding_it(client, db, tenant, member, member_headers, tenant_headers, gateway):
    product = await make_product(db, tenant)
    abandoned = ClientRequest(user_id=member.id, idempotency_key="died", endpoint="commerce-product-checkout")
    db.add(abandoned)
    await db.commit()

    abandoned.claimed_at = now() - timedelta(hours=1)
    await db.commit()

    answer = await client.post(f"/api/commerce/products/{product.slug}/checkout", json=BODY, headers=member_headers | tenant_headers | {HEADER: "died"})

    assert answer.status_code == 200
    assert gateway == [product.id]


async def test_only_one_of_the_calls_meeting_an_abandoned_name_takes_it_over(db, member):
    """The window is taken with an update, because two calls that read it and then decide both do the work."""
    abandoned = ClientRequest(user_id=member.id, idempotency_key="died-twice", endpoint="commerce-product-checkout")
    db.add(abandoned)
    await db.commit()

    abandoned.claimed_at = now() - timedelta(hours=1)
    await db.commit()

    assert await idempotency.take_over(db, abandoned) is True
    assert await idempotency.take_over(db, abandoned) is False


async def test_a_name_already_given_to_something_else_is_refused(client, db, tenant, member, member_headers, tenant_headers, gateway):
    product = await make_product(db, tenant)
    db.add(ClientRequest(user_id=member.id, idempotency_key="taken", endpoint="subscription-plan-checkout", answer={"url": "https://gateway.acme.com/plan"}))
    await db.commit()

    answer = await client.post(f"/api/commerce/products/{product.slug}/checkout", json=BODY, headers=member_headers | tenant_headers | {HEADER: "taken"})

    assert answer.status_code == 409
    assert answer.json()["code"] == "error.idempotency-key-reused"


async def test_a_name_belongs_to_the_account_that_used_it(client, db, tenant, administrator, member_headers, tenant_headers, gateway):
    """One client naming a write says nothing about another one, and two accounts share no key space."""
    product = await make_product(db, tenant)
    db.add(ClientRequest(user_id=administrator.id, idempotency_key="mine", endpoint="commerce-product-checkout", answer={"url": "https://gateway.acme.com/somebody-else"}))
    await db.commit()

    answer = await client.post(f"/api/commerce/products/{product.slug}/checkout", json=BODY, headers=member_headers | tenant_headers | {HEADER: "mine"})

    assert answer.status_code == 200
    assert answer.json()["url"] != "https://gateway.acme.com/somebody-else"


async def test_a_plan_checkout_answers_the_same_way_to_the_same_name(client, db, tenant, member_headers, tenant_headers, monkeypatch):
    """The two doors a buyer leaves through behave alike, because an application retries either of them."""
    from tests.factories import make_plan

    plan = await make_plan(db, tenant)
    opened = []

    async def answer(session, tenant_row, user, offered, success_url, cancel_url):
        opened.append(offered.id)

        return f"https://gateway.acme.com/plan/{len(opened)}"

    monkeypatch.setattr(checkout_service, "for_plan", answer)

    headers = member_headers | tenant_headers | {HEADER: "plan-abc"}
    first = await client.post(f"/api/subscriptions/plans/{plan.code}/checkout", json=BODY, headers=headers)
    second = await client.post(f"/api/subscriptions/plans/{plan.code}/checkout", json=BODY, headers=headers)

    assert first.json()["url"] == second.json()["url"]
    assert opened == [plan.id]


async def test_a_key_given_back_between_the_refused_insert_and_the_read_is_still_in_flight(db, member, monkeypatch):
    """The winner failed and gave the name back in the instant between, so there is nothing to read and the call is told to try again."""

    async def lost_and_gone(session, instance, read):
        return None

    monkeypatch.setattr(idempotency, "insert_or_read", lost_and_gone)

    with pytest.raises(ConflictError) as refused:
        await idempotency.claim(db, member, "one-key", "/api/commerce/products/x/checkout")

    assert refused.value.code == "error.idempotency-key-in-flight"
