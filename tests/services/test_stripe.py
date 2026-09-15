"""The Stripe gateway, read against the shape their current API documents."""

import hashlib
import hmac
import json
from datetime import timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

from enums.commerce import PurchaseStatus
from enums.integration import NormalizedAction, Provider, WebhookEventStatus
from enums.subscription import SubscriptionStatus
from helpers.dates import now
from helpers.errors import AuthenticationError
from helpers.security import encrypt
from models.commerce import Purchase, UserProduct
from models.integration import WebhookEvent
from models.subscription import Subscription
from services import webhook as module
from services.commerce import commerce_service
from services.gateway import TOLERANCE, InboundCall
from services.integration import integration_service
from tests.factories import make_benefit, make_entitlement, make_external_product, make_integration, make_plan, make_plan_entitlement, make_product

SECRET = "whsec_test_1"

STRIPE = module.PROVIDERS[Provider.STRIPE]


def signed(body: bytes, secret: str = SECRET, stamped: int | None = None, schemes: str = "v1") -> str:
    moment = stamped if stamped is not None else int(now().timestamp())
    digest = hmac.new(secret.encode(), f"{moment}.".encode() + body, hashlib.sha256).hexdigest()

    return f"t={moment},{schemes}={digest}"


def call_of(payload: dict, secret: str = SECRET, **overrides) -> InboundCall:
    body = json.dumps(payload).encode()

    return InboundCall(method="POST", headers={"content-type": "application/json", "stripe-signature": signed(body, secret, **overrides)}, body=body)


def subscription_event(event_type: str = "customer.subscription.updated", **entry) -> dict:
    moment = int(now().timestamp())
    body = {
        "id": "sub_1",
        "object": "subscription",
        "status": "active",
        "livemode": True,
        "start_date": moment - 86400,
        "metadata": {"account_token": entry.pop("account_token", "token-1")},
        "items": {"object": "list", "data": [{"id": "si_1", "current_period_start": moment - 3600, "current_period_end": moment + 2592000, "price": {"id": "price_1"}}]},
    }

    return {"id": "evt_1", "object": "event", "type": event_type, "created": moment, "data": {"object": body | entry}}


def session_event(event_type: str = "checkout.session.completed", created=None, **entry) -> dict:
    return {
        "id": "evt_2",
        "object": "event",
        "type": event_type,
        "created": int(now().timestamp()) if created is None else created,
        "data": {"object": {"id": "cs_1", "object": "checkout.session", "mode": "payment", "payment_status": "paid", "payment_intent": "pi_1", "amount_total": 1990, "currency": "usd", "client_reference_id": "ref-1", "metadata": {"account_token": "token-1"}} | entry},
    }


def dispute_event(status: str, event_id: str = "evt_5", **entry) -> dict:
    """What a dispute arrives as, where the object names the same payment intent a session stored."""
    return {"id": event_id, "object": "event", "type": "charge.dispute.closed", "created": int(now().timestamp()), "data": {"object": {"id": "du_1", "object": "dispute", "charge": "ch_1", "payment_intent": "pi_1", "amount": 1990, "currency": "usd", "status": status} | entry}}


def charge_event(event_type: str = "charge.refunded", **entry) -> dict:
    """What a refund arrives as, where the charge names the payment intent and never the reference this side minted."""
    return {"id": "evt_3", "object": "event", "type": event_type, "created": int(now().timestamp()), "data": {"object": {"id": "ch_1", "object": "charge", "payment_intent": "pi_1", "amount": 1990, "amount_refunded": 1990, "refunded": True, "currency": "usd"} | entry}}


@pytest.fixture
async def wired(db, tenant, member):
    integration = await make_integration(db, tenant, provider=Provider.STRIPE, stripe_api_key_encrypted=encrypt("sk_test_1"), stripe_webhook_secret_encrypted=encrypt(SECRET))
    plan = await make_plan(db, tenant)
    entitlement = await make_entitlement(db, tenant)

    await make_plan_entitlement(db, plan, entitlement)
    await make_benefit(db, entitlement, target="access")
    await make_external_product(db, integration, plan, external_id="price_1")

    return integration


def test_a_call_signed_with_the_endpoint_secret_is_accepted(wired):
    call = call_of(subscription_event())

    STRIPE.authenticate(wired, call, SECRET)

    assert call.header("stripe-signature")


def test_a_call_signed_with_another_secret_is_refused(wired):
    with pytest.raises(AuthenticationError):
        STRIPE.authenticate(wired, call_of(subscription_event(), secret="whsec_somebody_else"), SECRET)


def test_a_call_with_no_signature_is_refused(wired):
    body = json.dumps(subscription_event()).encode()

    with pytest.raises(AuthenticationError):
        STRIPE.authenticate(wired, InboundCall(method="POST", headers={"content-type": "application/json"}, body=body), SECRET)


def test_a_signature_carrying_no_v1_is_refused(wired):
    """Only v1 counts, because taking any other scheme is what a downgrade attack asks for."""
    with pytest.raises(AuthenticationError):
        STRIPE.authenticate(wired, call_of(subscription_event(), schemes="v0"), SECRET)


def test_a_signature_with_no_timestamp_is_refused(wired):
    body = json.dumps(subscription_event()).encode()

    with pytest.raises(AuthenticationError):
        STRIPE.authenticate(wired, InboundCall(method="POST", headers={"content-type": "application/json", "stripe-signature": "v1=deadbeef"}, body=body), SECRET)


def test_a_timestamp_outside_the_tolerance_is_a_replay_and_never_a_redelivery(wired):
    """Stripe stamps a fresh timestamp on every retry, so an old one is a call somebody kept."""
    old = int((now() - TOLERANCE - timedelta(seconds=10)).timestamp())

    with pytest.raises(AuthenticationError):
        STRIPE.authenticate(wired, call_of(subscription_event(), stamped=old), SECRET)


def test_a_timestamp_that_is_not_a_number_is_refused(wired):
    body = json.dumps(subscription_event()).encode()

    with pytest.raises(AuthenticationError):
        STRIPE.authenticate(wired, InboundCall(method="POST", headers={"content-type": "application/json", "stripe-signature": "t=yesterday,v1=deadbeef"}, body=body), SECRET)


def test_a_secret_being_rolled_signs_twice_and_either_one_answers(wired):
    """Stripe keeps the previous secret alive for a day, and one signature per secret is what it sends while it does."""
    body = json.dumps(subscription_event()).encode()
    moment = int(now().timestamp())
    old = hmac.new(b"whsec_the_old_one", f"{moment}.".encode() + body, hashlib.sha256).hexdigest()
    current = hmac.new(SECRET.encode(), f"{moment}.".encode() + body, hashlib.sha256).hexdigest()

    call = InboundCall(method="POST", headers={"content-type": "application/json", "stripe-signature": f"t={moment},v1={old},v1={current}"}, body=body)

    STRIPE.authenticate(wired, call, SECRET)

    assert call.header("stripe-signature").count("v1=") == 2


async def test_an_integration_with_no_secret_takes_the_call_as_it_comes(db, tenant):
    """The drawn key in the address is what stands for the endpoint until somebody pastes a signing secret."""
    integration = await make_integration(db, tenant, provider=Provider.STRIPE)
    body = json.dumps(subscription_event()).encode()

    STRIPE.authenticate(integration, InboundCall(method="POST", headers={}, body=body), "")

    assert integration_service.read_webhook_secret(integration) is None


async def test_a_body_that_is_not_an_event_is_read_as_nothing(wired):
    assert await STRIPE.read(wired, call_of({"hello": "there"}), None) is None
    assert await STRIPE.read(wired, call_of({"object": "event"}), None) is None


async def test_a_subscription_event_carries_the_state_it_resolved(wired):
    event = await STRIPE.read(wired, call_of(subscription_event()), None)

    assert event.account_token == "token-1"
    assert event.product_reference == "price_1"
    assert len(event.state) == 1
    assert event.state[0].external_id == "sub_1"
    assert event.state[0].status == SubscriptionStatus.ACTIVE
    assert event.state[0].period_ends_at is not None


@pytest.mark.parametrize(
    "status,expected",
    [
        ("trialing", SubscriptionStatus.TRIALING),
        ("active", SubscriptionStatus.ACTIVE),
        ("past_due", SubscriptionStatus.GRACE_PERIOD),
        ("unpaid", SubscriptionStatus.GRACE_PERIOD),
        ("paused", SubscriptionStatus.SUSPENDED),
        ("incomplete", SubscriptionStatus.PENDING),
        ("incomplete_expired", SubscriptionStatus.EXPIRED),
        ("canceled", SubscriptionStatus.EXPIRED),
    ],
)
async def test_every_status_stripe_names_becomes_one_of_ours(wired, status, expected):
    event = await STRIPE.read(wired, call_of(subscription_event(status=status)), None)

    assert event.state[0].status == expected


async def test_a_trial_is_read_as_one(wired):
    event = await STRIPE.read(wired, call_of(subscription_event(status="trialing")), None)

    assert event.state[0].trial is True


async def test_a_paused_collection_says_when_it_comes_back(wired):
    resumes = int((now() + timedelta(days=10)).timestamp())
    event = await STRIPE.read(wired, call_of(subscription_event(pause_collection={"behavior": "void", "resumes_at": resumes})), None)

    assert event.state[0].auto_resume_at is not None
    assert event.action == NormalizedAction.SUSPEND


async def test_a_cancellation_at_the_end_of_the_period_is_named_as_one(wired):
    event = await STRIPE.read(wired, call_of(subscription_event(cancel_at_period_end=True, canceled_at=int(now().timestamp()))), None)

    assert event.action == NormalizedAction.CANCEL_AT_PERIOD_END
    assert event.state[0].unsubscribed_at is not None


async def test_an_update_the_object_says_nothing_about_carries_no_action(wired):
    """The notice is still recorded and still writes the state, because what it was about is what has no name."""
    event = await STRIPE.read(wired, call_of(subscription_event()), None)

    assert event.action is None
    assert event.state is not None


@pytest.mark.parametrize("event_type,expected", [("customer.subscription.created", NormalizedAction.ACTIVATE), ("customer.subscription.deleted", NormalizedAction.EXPIRE), ("customer.subscription.paused", NormalizedAction.SUSPEND), ("customer.subscription.resumed", NormalizedAction.RESUME)])
async def test_the_events_that_name_themselves_are_named(wired, event_type, expected):
    event = await STRIPE.read(wired, call_of(subscription_event(event_type)), None)

    assert event.action == expected


async def test_an_event_about_anything_but_a_subscription_resolves_no_state(wired):
    """A notice about a charge says nothing about what the account holds, and reading it as everything would close it all."""
    body = {"id": "evt_3", "object": "event", "type": "charge.refunded", "created": int(now().timestamp()), "data": {"object": {"id": "ch_1", "object": "charge", "metadata": {"account_token": "token-1"}}}}
    event = await STRIPE.read(wired, call_of(body), None)

    assert event.action == NormalizedAction.REFUND
    assert event.state is None


async def test_a_subscription_with_no_item_still_reads(wired):
    event = await STRIPE.read(wired, call_of(subscription_event(items={"object": "list", "data": []})), None)

    assert event.state[0].product_reference == ""
    assert event.state[0].period_ends_at is None


async def test_the_environment_follows_the_mode_the_object_was_made_in(wired):
    live = await STRIPE.read(wired, call_of(subscription_event()), None)
    sandbox = await STRIPE.read(wired, call_of(subscription_event(livemode=False)), None)

    assert live.state[0].environment == "production"
    assert sandbox.state[0].environment == "sandbox"


@pytest.mark.parametrize("amount,currency,expected", [(1990, "usd", Decimal("19.90")), (1990, "jpy", Decimal("1990")), (1990, "bhd", Decimal("1.990"))])
def test_an_amount_is_read_in_the_units_of_its_own_currency(amount, currency, expected):
    """A zero decimal currency has no cents, and dividing one by a hundred says somebody paid a hundredth of what they did."""
    assert STRIPE.money(amount, currency) == expected


def test_an_amount_with_no_currency_is_no_amount():
    assert STRIPE.money(1990, None) is None
    assert STRIPE.money(None, "usd") is None


@pytest.mark.parametrize("payment_status,expected", [("paid", PurchaseStatus.PAID), ("unpaid", PurchaseStatus.PENDING), ("no_payment_required", PurchaseStatus.PAID)])
async def test_a_checkout_session_says_what_became_of_the_payment(wired, payment_status, expected):
    """A method that settles days later leaves the session unpaid, so unpaid is a payment on its way and never one that failed."""
    event = await STRIPE.read(wired, call_of(session_event(payment_status=payment_status)), None)

    assert event.purchase_status == expected
    assert event.reference == "ref-1"
    assert event.amount == Decimal("19.90")


@pytest.mark.parametrize("event_type,expected", [("checkout.session.async_payment_succeeded", PurchaseStatus.PAID), ("checkout.session.async_payment_failed", PurchaseStatus.FAILED), ("checkout.session.expired", PurchaseStatus.CANCELED)])
async def test_a_delayed_payment_says_how_it_ended_in_an_event_of_its_own(wired, event_type, expected):
    """A boleto leaves the session unpaid for days, so what became of it is the later event and never the payment status."""
    event = await STRIPE.read(wired, call_of(session_event(event_type, payment_status="unpaid")), None)

    assert event.purchase_status == expected


async def test_a_session_that_opened_a_subscription_says_nothing_about_a_payment_of_ours(wired):
    """A subscription mode session is the gateway opening a recurring charge, and the purchase table is not what it names."""
    event = await STRIPE.read(wired, call_of(session_event(mode="subscription")), None)

    assert event.purchase_status is None


async def test_a_notice_about_a_subscription_opens_it_on_this_side(db, client, tenant, member, wired):
    payload = subscription_event("customer.subscription.created", account_token=member.token)

    answer = await client.post(f"/api/webhooks/{wired.webhook_key}", content=json.dumps(payload), headers={"content-type": "application/json", "stripe-signature": signed(json.dumps(payload).encode())})

    assert answer.status_code == 200

    subscription = await db.scalar(select(Subscription))

    assert subscription.user_id == member.id
    assert subscription.status == SubscriptionStatus.ACTIVE


async def test_the_same_notice_twice_is_one_row_and_one_reading(db, client, tenant, member, wired):
    payload = subscription_event("customer.subscription.created", account_token=member.token)
    body = json.dumps(payload)

    for _ in range(2):
        await client.post(f"/api/webhooks/{wired.webhook_key}", content=body, headers={"content-type": "application/json", "stripe-signature": signed(body.encode())})

    assert len((await db.execute(select(WebhookEvent))).scalars().all()) == 1
    assert len((await db.execute(select(Subscription))).scalars().all()) == 1


async def test_a_notice_about_a_payment_settles_the_purchase_it_names(db, client, tenant, member, wired):
    product = await make_product(db, tenant, name="The Handbook")
    purchase = await commerce_service.open_purchase(db, tenant, member, product, wired.id)

    payload = session_event(client_reference_id=purchase.reference, metadata={"account_token": member.token})
    body = json.dumps(payload)

    answer = await client.post(f"/api/webhooks/{wired.webhook_key}", content=body, headers={"content-type": "application/json", "stripe-signature": signed(body.encode())})

    assert answer.status_code == 200

    await db.refresh(purchase)

    assert purchase.status == PurchaseStatus.PAID
    assert purchase.external_id == "pi_1", "a refund names the intent, so the intent is what this side stores"
    assert await db.scalar(select(UserProduct).where(UserProduct.user_id == member.id)) is not None


async def test_a_reference_naming_no_purchase_of_ours_changes_nothing(db, client, tenant, member, wired):
    payload = session_event(client_reference_id="ref-nobody-minted", metadata={"account_token": member.token})
    body = json.dumps(payload)

    answer = await client.post(f"/api/webhooks/{wired.webhook_key}", content=body, headers={"content-type": "application/json", "stripe-signature": signed(body.encode())})

    assert answer.status_code == 200
    assert await db.scalar(select(Purchase)) is None


async def test_a_notice_never_closes_what_it_says_nothing_about(db, client, tenant, member, wired):
    """A Stripe notice is about one subscription, so a second one the account holds is not a leftover."""
    from tests.factories import make_subscription

    other = await make_subscription(db, tenant, member, await make_plan(db, tenant, code="yearly"), integration_id=wired.id, external_id="sub_other")

    payload = subscription_event("customer.subscription.created", account_token=member.token)
    body = json.dumps(payload)

    await client.post(f"/api/webhooks/{wired.webhook_key}", content=body, headers={"content-type": "application/json", "stripe-signature": signed(body.encode())})
    await db.refresh(other)

    assert other.status == SubscriptionStatus.ACTIVE


async def test_a_notice_this_side_cannot_read_is_written_down_unread(db, client, tenant, wired):
    body = json.dumps({"hello": "there"})

    answer = await client.post(f"/api/webhooks/{wired.webhook_key}", content=body, headers={"content-type": "application/json", "stripe-signature": signed(body.encode())})

    assert answer.status_code == 200

    record = await db.scalar(select(WebhookEvent))

    assert record.status == WebhookEventStatus.IGNORED
    assert record.error_code == "unread"


async def test_a_forged_notice_never_reaches_the_payload(db, client, tenant, wired):
    body = json.dumps(subscription_event())

    answer = await client.post(f"/api/webhooks/{wired.webhook_key}", content=body, headers={"content-type": "application/json", "stripe-signature": signed(body.encode(), secret="whsec_forged")})

    assert answer.status_code == 401
    assert await db.scalar(select(WebhookEvent)) is None


async def test_stripe_is_never_asked_what_an_account_holds(wired):
    """Its notice carries the object, so nothing here has a key to read a subscriber with."""
    assert STRIPE.queryable is False
    assert STRIPE.event_stated is True


async def test_a_notice_about_an_account_of_another_tenant_is_ignored(db, client, tenant, wired):
    payload = subscription_event("customer.subscription.created", account_token="a-token-nobody-here-has")
    body = json.dumps(payload)

    answer = await client.post(f"/api/webhooks/{wired.webhook_key}", content=body, headers={"content-type": "application/json", "stripe-signature": signed(body.encode())})

    assert answer.status_code == 200

    record = await db.scalar(select(WebhookEvent))

    assert record.status == WebhookEventStatus.IGNORED
    assert record.error_code == "unresolved"


async def test_a_redelivered_notice_never_unsettles_a_payment_that_already_landed(db, tenant, member):
    """Stripe redelivers the notice that opened a delayed payment for days, and by then the money may already be in."""
    product = await make_product(db, tenant)
    purchase = await commerce_service.open_purchase(db, tenant, member, product, None)

    await commerce_service.settle_purchase(db, purchase, PurchaseStatus.PAID)
    await commerce_service.settle_purchase(db, purchase, PurchaseStatus.PENDING)

    assert purchase.status == PurchaseStatus.PAID


async def test_money_that_went_back_is_still_written_over_a_paid_purchase(db, tenant, member):
    product = await make_product(db, tenant)
    purchase = await commerce_service.open_purchase(db, tenant, member, product, None)

    await commerce_service.settle_purchase(db, purchase, PurchaseStatus.PAID)
    await commerce_service.settle_purchase(db, purchase, PurchaseStatus.REFUNDED)

    assert purchase.status == PurchaseStatus.REFUNDED


@pytest.mark.parametrize("stamp", ["not-a-number", "17.5", 10**25, {"nested": 1}])
async def test_a_stamp_nothing_can_read_never_costs_the_whole_notice(wired, stamp):
    """The event is read before it is written down, so a raise here loses what arrived and the gateway retries into nothing."""
    event = await STRIPE.read(wired, call_of(session_event(created=stamp)), None)

    assert event is not None
    assert event.occurred_at is None
    assert event.reference == "ref-1"


async def send(client, wired, payload: dict):
    body = json.dumps(payload)

    return await client.post(f"/api/webhooks/{wired.webhook_key}", content=body, headers={"content-type": "application/json", "stripe-signature": signed(body.encode())})


async def paid_purchase(db, client, tenant, member, wired):
    product = await make_product(db, tenant, name="The Handbook")
    purchase = await commerce_service.open_purchase(db, tenant, member, product, wired.id)

    await send(client, wired, session_event(client_reference_id=purchase.reference, metadata={"account_token": member.token}))
    await db.refresh(purchase)

    return purchase


async def test_a_charge_that_went_back_in_full_marks_the_purchase_it_names(db, client, tenant, member, wired):
    """A charge carries no reference of ours, so what names the purchase is the payment stored when the session settled."""
    purchase = await paid_purchase(db, client, tenant, member, wired)

    assert (await send(client, wired, charge_event())).status_code == 200

    await db.refresh(purchase)

    assert purchase.status == PurchaseStatus.REFUNDED
    # The money went back and the product does not, which is what this side decided a refund means.
    assert await db.scalar(select(UserProduct).where(UserProduct.user_id == member.id)) is not None


async def test_a_charge_only_partly_refunded_leaves_the_purchase_where_it_stands(db, client, tenant, member, wired):
    """Stripe raises `refunded` only where the whole charge went back, and half of it going back is not a purchase undone."""
    purchase = await paid_purchase(db, client, tenant, member, wired)

    assert (await send(client, wired, charge_event(refunded=False, amount_refunded=500))).status_code == 200

    await db.refresh(purchase)

    assert purchase.status == PurchaseStatus.PAID


async def test_a_charge_naming_a_payment_this_side_never_stored_changes_nothing(db, client, tenant, member, wired):
    purchase = await paid_purchase(db, client, tenant, member, wired)

    assert (await send(client, wired, charge_event(payment_intent="pi_nobody_stored"))).status_code == 200

    await db.refresh(purchase)

    assert purchase.status == PurchaseStatus.PAID


async def test_a_payment_naming_neither_key_moves_nothing(db, client, tenant, member, wired):
    """A session opened outside this application carries no reference of ours, and a charge without an intent names nothing this side stored."""
    purchase = await paid_purchase(db, client, tenant, member, wired)

    named_by_nothing = session_event(client_reference_id=None, payment_intent=None) | {"id": "evt_4"}

    assert (await send(client, wired, named_by_nothing)).status_code == 200

    await db.refresh(purchase)

    assert purchase.status == PurchaseStatus.PAID


async def test_a_dispute_the_merchant_lost_marks_the_purchase_charged_back(db, client, tenant, member, wired):
    """Lost is the money gone for good, which is the only thing a chargeback means."""
    purchase = await paid_purchase(db, client, tenant, member, wired)

    assert (await send(client, wired, dispute_event("lost"))).status_code == 200

    await db.refresh(purchase)

    assert purchase.status == PurchaseStatus.CHARGED_BACK


async def test_a_dispute_the_merchant_won_leaves_the_payment_standing(db, client, tenant, member, wired):
    """Won is the money kept, so the purchase is paid again and never left saying it was taken."""
    purchase = await paid_purchase(db, client, tenant, member, wired)

    await send(client, wired, dispute_event("lost"))
    await send(client, wired, dispute_event("won", event_id="evt_6"))
    await db.refresh(purchase)

    assert purchase.status == PurchaseStatus.PAID


@pytest.mark.parametrize("status", ["needs_response", "under_review", "warning_needs_response", "prevented"])
async def test_a_dispute_still_being_argued_moves_nothing(db, client, tenant, member, wired, status):
    """A dispute opened is not a chargeback, and one Stripe prevented never became a formal one at all."""
    purchase = await paid_purchase(db, client, tenant, member, wired)

    assert (await send(client, wired, dispute_event(status))).status_code == 200

    await db.refresh(purchase)

    assert purchase.status == PurchaseStatus.PAID
