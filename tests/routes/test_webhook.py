import hashlib
import hmac
import json
from datetime import timedelta
from decimal import Decimal

import httpx
import pytest
from sqlalchemy import select

from enums.integration import NormalizedAction, Provider, WebhookEventStatus
from enums.subscription import SubscriptionStatus
from helpers.dates import now
from helpers.security import encrypt
from models.integration import ExternalProduct, WebhookEvent
from models.subscription import Subscription
from services.gateway import TOLERANCE
from tests.factories import make_integration, make_plan, save

SECRET = "sk-revenuecat"


def instant(days: float) -> str:
    return (now() + timedelta(days=days)).isoformat().replace("+00:00", "Z")


def holds(**overrides) -> dict:
    return {"expires_date": instant(30), "period_type": "NORMAL", "store": "APP_STORE", "is_sandbox": False, "store_transaction_id": "txn-1", "purchase_date": instant(-1)} | overrides


def answering(subscriptions: dict | None = None):
    async def responder(self, request):
        return httpx.Response(200, json={"subscriber": {"subscriptions": subscriptions if subscriptions is not None else {"mensal": holds()}}})

    return responder


async def wire(db, tenant, member, **overrides):
    integration = await make_integration(db, tenant, provider=Provider.REVENUECAT, revenuecat_api_key_encrypted=encrypt(SECRET), **overrides)
    plan = await make_plan(db, tenant)

    await save(db, ExternalProduct(integration_id=integration.id, plan_id=plan.id, external_id="mensal", active=True, meta={}))

    return integration, plan


def event(kind: str, member, **overrides) -> dict:
    payload = {"id": "evt-1", "type": kind, "app_user_id": member.token, "product_id": "mensal", "original_transaction_id": "txn-1", "price": 3.9, "price_in_purchased_currency": 19.9, "currency": "BRL", "environment": "PRODUCTION"} | overrides

    return {"api_version": "1.0", "event": payload}


@pytest.fixture(autouse=True)
def provider_answers(monkeypatch):
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", answering())


async def test_an_event_is_a_trigger_and_what_the_provider_holds_is_what_is_written(client, db, tenant, member):
    """The body of an event never decides the state, so a lost or reordered one can never leave a wrong answer behind."""
    integration, plan = await wire(db, tenant, member)

    response = await client.post(f"/api/webhooks/{integration.webhook_key}", json=event("INITIAL_PURCHASE", member))
    subscription = await db.scalar(select(Subscription))

    assert response.json() == {"status": "completed", "action": "activate"}
    assert subscription.status == SubscriptionStatus.ACTIVE
    assert subscription.plan_id == plan.id


async def test_an_event_whose_type_this_side_never_learned_still_reads_the_account(client, db, tenant, member):
    """What matters is that something moved for that account, and the provider is asked what it was."""
    integration, _ = await wire(db, tenant, member)

    response = await client.post(f"/api/webhooks/{integration.webhook_key}", json=event("PAYWALL_IMPRESSION", member))

    assert response.json()["status"] == WebhookEventStatus.COMPLETED
    assert await db.scalar(select(Subscription)) is not None


async def test_the_same_event_arriving_twice_is_one_row_and_one_reading(client, db, tenant, member):
    integration, _ = await wire(db, tenant, member)
    payload = event("INITIAL_PURCHASE", member)

    await client.post(f"/api/webhooks/{integration.webhook_key}", json=payload)
    await client.post(f"/api/webhooks/{integration.webhook_key}", json=payload)

    events = (await db.execute(select(WebhookEvent))).scalars().all()
    subscriptions = (await db.execute(select(Subscription))).scalars().all()

    assert len(events) == 1
    assert len(subscriptions) == 1


async def test_a_row_another_delivery_already_wrote_is_read_instead_of_erroring(db, tenant, member):
    from services import webhook as module

    integration, _ = await wire(db, tenant, member)

    def arriving():
        return WebhookEvent(tenant_id=tenant.id, integration_id=integration.id, external_event_id="evt-race", payload_hash="h", status=WebhookEventStatus.RECEIVED, payload={}, meta={})

    winner = await module.webhook_service.store(db, arriving())
    loser = await module.webhook_service.store(db, arriving())

    assert loser.id == winner.id


async def test_an_event_naming_an_account_of_another_tenant_is_ignored(client, db, tenant, member):
    integration, _ = await wire(db, tenant, member)

    response = await client.post(f"/api/webhooks/{integration.webhook_key}", json=event("INITIAL_PURCHASE", member, app_user_id="00000000-0000-0000-0000-000000000000"))
    record = await db.scalar(select(WebhookEvent))

    assert response.json()["status"] == WebhookEventStatus.IGNORED
    assert record.error_code == "unresolved"
    assert await db.scalar(select(Subscription)) is None


async def test_an_event_naming_nobody_is_ignored(client, db, tenant, member):
    integration, _ = await wire(db, tenant, member)

    response = await client.post(f"/api/webhooks/{integration.webhook_key}", json=event("INITIAL_PURCHASE", member, app_user_id=None))

    assert response.json()["status"] == WebhookEventStatus.IGNORED


async def test_the_kind_of_event_is_kept_for_the_operator_to_read(client, db, tenant, member):
    """It decides nothing, and it is still what the grid of events is filtered and understood by."""
    integration, _ = await wire(db, tenant, member)

    await client.post(f"/api/webhooks/{integration.webhook_key}", json=event("CANCELLATION", member, cancel_reason="CUSTOMER_SUPPORT"))
    record = await db.scalar(select(WebhookEvent))

    # The name the gateway gave it stays in the payload, and what this side acts on is the action it became.
    assert record.payload["event"]["type"] == "CANCELLATION"
    assert record.action == NormalizedAction.REFUND


async def test_what_the_buyer_paid_is_kept_in_the_currency_they_paid_it(client, db, tenant, member, member_headers):
    """What `price` carries is the dollar figure, and `price_in_purchased_currency` is the money that left their account."""
    integration, _ = await wire(db, tenant, member)

    await client.post(f"/api/webhooks/{integration.webhook_key}", json=event("INITIAL_PURCHASE", member))

    subscription = await db.scalar(select(Subscription))
    items = (await client.get(f"/api/subscriptions/{subscription.id}/transactions", headers=member_headers)).json()["items"]

    assert Decimal(items[0]["amount"]) == Decimal("19.90")
    assert items[0]["currency"] == "BRL"


async def test_a_sandbox_event_is_read_like_any_other(client, db, tenant, member):
    """A test purchase has to work end to end, or there is no way to test the thing that takes money."""
    integration, _ = await wire(db, tenant, member)

    response = await client.post(f"/api/webhooks/{integration.webhook_key}", json=event("INITIAL_PURCHASE", member, environment="SANDBOX"))

    assert response.json()["status"] == WebhookEventStatus.COMPLETED


async def test_a_gateway_that_calls_with_get_is_answered_the_same(client, db, tenant):
    integration = await make_integration(db, tenant, provider=Provider.STRIPE)

    response = await client.get(f"/api/webhooks/{integration.webhook_key}?topic=payment&id=123")
    record = await db.scalar(select(WebhookEvent))

    assert response.status_code == 200
    assert record.meta["method"] == "GET"
    assert record.meta["query"] == {"topic": "payment", "id": "123"}


async def test_a_gateway_that_posts_a_form_is_written_down_whole(client, db, tenant):
    integration = await make_integration(db, tenant, provider=Provider.STRIPE)

    await client.post(f"/api/webhooks/{integration.webhook_key}", data={"type": "payment", "data_id": "123"})
    record = await db.scalar(select(WebhookEvent))

    assert record.payload == {"type": "payment", "data_id": "123"}


async def test_a_body_that_is_not_json_at_all_is_kept_as_it_came(client, db, tenant):
    integration = await make_integration(db, tenant, provider=Provider.STRIPE)

    await client.post(f"/api/webhooks/{integration.webhook_key}", content=b"<xml><pago/></xml>", headers={"Content-Type": "application/xml"})
    record = await db.scalar(select(WebhookEvent))

    assert record.payload == {"body": "<xml><pago/></xml>"}


async def test_the_headers_are_kept_except_the_one_that_proves_who_called(client, db, tenant):
    integration = await make_integration(db, tenant, provider=Provider.STRIPE)

    await client.post(f"/api/webhooks/{integration.webhook_key}", json={"type": "payment"}, headers={"Authorization": "segredo", "X-Signature": "ts=1,v1=abc"})
    record = await db.scalar(select(WebhookEvent))

    assert record.meta["headers"]["x-signature"] == "ts=1,v1=abc"
    assert "authorization" not in record.meta["headers"]


async def test_a_call_that_carries_nothing_is_not_written_down(client, db, tenant):
    """A gateway probing the address is not an event, and a row for every probe would be noise forever."""
    integration = await make_integration(db, tenant, provider=Provider.STRIPE)

    response = await client.get(f"/api/webhooks/{integration.webhook_key}")

    assert response.status_code == 200
    assert await db.scalar(select(WebhookEvent)) is None


async def test_a_json_body_that_is_not_what_the_gateway_sends_is_kept_and_not_read(client, db, tenant, member):
    integration, _ = await wire(db, tenant, member)

    response = await client.post(f"/api/webhooks/{integration.webhook_key}", json={"hello": "world"})
    record = await db.scalar(select(WebhookEvent))

    assert response.json()["status"] == WebhookEventStatus.IGNORED
    assert record.error_code == "unread"


async def test_a_wrong_secret_never_reaches_the_payload(client, db, tenant, member):
    integration, _ = await wire(db, tenant, member, revenuecat_webhook_secret_encrypted=encrypt("whsec-certo"))

    wrong = await client.post(f"/api/webhooks/{integration.webhook_key}", json=event("INITIAL_PURCHASE", member), headers={"Authorization": "whsec-errado"})
    missing = await client.post(f"/api/webhooks/{integration.webhook_key}", json=event("INITIAL_PURCHASE", member))

    assert wrong.status_code == 401
    assert wrong.json()["code"] == "error.webhook-signature-invalid"
    assert missing.status_code == 401
    assert await db.scalar(select(WebhookEvent)) is None


async def test_a_secret_carrying_anything_but_ascii_is_refused_and_never_crashes(client, db, tenant, member):
    """A header arrives as bytes and is read back as latin-1, and comparing that as text raises where the answer owed is a plain refusal."""
    integration, _ = await wire(db, tenant, member, revenuecat_webhook_secret_encrypted=encrypt("whsec-certo"))

    response = await client.post(f"/api/webhooks/{integration.webhook_key}", json=event("INITIAL_PURCHASE", member), headers={"Authorization": "whsec-çerto".encode("latin-1")})

    assert response.status_code == 401
    assert response.json()["code"] == "error.webhook-signature-invalid"


async def test_the_right_secret_gets_through(client, db, tenant, member):
    integration, _ = await wire(db, tenant, member, revenuecat_webhook_secret_encrypted=encrypt("whsec-certo"))

    response = await client.post(f"/api/webhooks/{integration.webhook_key}", json=event("INITIAL_PURCHASE", member), headers={"Authorization": "whsec-certo"})

    assert response.status_code == 200


async def test_a_signed_call_is_verified_against_the_body_that_arrived(client, db, tenant, member):
    """The signature covers `<t>.<raw body>`, so anything that reserializes the body would fail a valid call."""
    integration, _ = await wire(db, tenant, member, revenuecat_webhook_secret_encrypted=encrypt("assinatura-secreta"))
    body = json.dumps(event("INITIAL_PURCHASE", member)).encode()
    stamp = int(now().timestamp())
    signature = hmac.new(b"assinatura-secreta", f"{stamp}.".encode() + body, hashlib.sha256).hexdigest()

    right = await client.post(f"/api/webhooks/{integration.webhook_key}", content=body, headers={"Content-Type": "application/json", "X-RevenueCat-Webhook-Signature": f"t={stamp},v1={signature}"})
    wrong = await client.post(f"/api/webhooks/{integration.webhook_key}", content=body, headers={"Content-Type": "application/json", "X-RevenueCat-Webhook-Signature": f"t={stamp},v1=deadbeef"})
    malformed = await client.post(f"/api/webhooks/{integration.webhook_key}", content=body, headers={"Content-Type": "application/json", "X-RevenueCat-Webhook-Signature": "sem-nada"})

    assert right.status_code == 200
    assert wrong.status_code == 401
    assert malformed.status_code == 401


async def test_a_secret_being_rolled_signs_twice_and_either_one_answers(client, db, tenant, member):
    """The header is read by the one parser both gateways share, so a secret in rotation is not refused on one of them and taken on the other."""
    integration, _ = await wire(db, tenant, member, revenuecat_webhook_secret_encrypted=encrypt("o-atual"))
    body = json.dumps(event("INITIAL_PURCHASE", member)).encode()
    stamp = int(now().timestamp())
    old = hmac.new(b"o-anterior", f"{stamp}.".encode() + body, hashlib.sha256).hexdigest()
    current = hmac.new(b"o-atual", f"{stamp}.".encode() + body, hashlib.sha256).hexdigest()

    # Which of the two comes first is the gateway's business, so both orders are the same call.
    for header in (f"t={stamp},v1={old},v1={current}", f"t={stamp},v1={current},v1={old}"):
        assert (await client.post(f"/api/webhooks/{integration.webhook_key}", content=body, headers={"Content-Type": "application/json", "X-RevenueCat-Webhook-Signature": header})).status_code == 200


async def test_an_address_nobody_owns_answers_not_found(client):
    assert (await client.post("/api/webhooks/chave-que-nao-existe", json={"event": {}})).status_code == 404


async def test_an_integration_that_is_off_answers_nothing(client, db, tenant, member):
    integration, _ = await wire(db, tenant, member, active=False)

    assert (await client.post(f"/api/webhooks/{integration.webhook_key}", json=event("INITIAL_PURCHASE", member))).status_code == 404


async def test_a_provider_with_no_reading_is_still_written_down(client, db, tenant):
    """Losing what arrived is worse than not reading it, and this row is what a parser is written against."""
    integration = await make_integration(db, tenant, provider=Provider.STRIPE)

    response = await client.post(f"/api/webhooks/{integration.webhook_key}", json={"action": "payment.created", "data": {"id": "123"}})
    record = await db.scalar(select(WebhookEvent))

    assert response.json()["status"] == WebhookEventStatus.IGNORED
    assert record.error_code == "unread"
    assert record.payload["action"] == "payment.created"


async def test_each_tenant_answers_only_for_its_own_address(client, db, tenant, member):
    first, _ = await wire(db, tenant, member)
    second = await make_integration(db, tenant, provider=Provider.STRIPE)

    assert first.webhook_key != second.webhook_key

    response = await client.post(f"/api/webhooks/{second.webhook_key}", json=event("INITIAL_PURCHASE", member))

    assert response.json()["status"] == WebhookEventStatus.IGNORED
    assert await db.scalar(select(Subscription)) is None


async def test_an_event_that_breaks_is_kept_and_the_failure_is_raised(db, tenant, member, monkeypatch):
    """The provider retries what did not stick, so the arrival is durable before anything reads it."""
    from services import webhook as module

    integration, _ = await wire(db, tenant, member)
    integration_id = integration.id
    call = module.InboundCall(method="POST", headers={"content-type": "application/json"}, body=json.dumps(event("INITIAL_PURCHASE", member)).encode())

    async def explode(*args, **kwargs):
        raise RuntimeError("the reconciliation fell over")

    monkeypatch.setattr(module.PROVIDERS[Provider.REVENUECAT], "state_from_query", explode)

    with pytest.raises(RuntimeError):
        await module.webhook_service.ingest(db, integration, call)

    record = await db.scalar(select(WebhookEvent).where(WebhookEvent.integration_id == integration_id))

    assert record.status == WebhookEventStatus.FAILED
    assert record.error_code == "RuntimeError"
    assert record.attempts == 1


async def test_what_failed_is_picked_up_by_this_side_after_the_gateway_gives_up(db, tenant, member, monkeypatch):
    from services import webhook as module

    integration, _ = await wire(db, tenant, member)
    integration_id = integration.id
    call = module.InboundCall(method="POST", headers={"content-type": "application/json"}, body=json.dumps(event("INITIAL_PURCHASE", member)).encode())

    async def explode(*args, **kwargs):
        raise RuntimeError("fell over")

    monkeypatch.setattr(module.PROVIDERS[Provider.REVENUECAT], "state_from_query", explode)

    with pytest.raises(RuntimeError):
        await module.webhook_service.ingest(db, integration, call)

    monkeypatch.undo()
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", answering())

    done = await module.webhook_service.retry_failed(db)
    record = await db.scalar(select(WebhookEvent).where(WebhookEvent.integration_id == integration_id))

    assert len(done) == 1
    assert record.status == WebhookEventStatus.COMPLETED
    assert record.attempts == 2


async def test_the_retry_gives_up_on_what_it_cannot_read(db, tenant, member):
    from services import webhook as module

    integration, _ = await wire(db, tenant, member)

    await save(db, WebhookEvent(tenant_id=tenant.id, integration_id=integration.id, external_event_id="y", payload_hash="y", error_code="unread", status=WebhookEventStatus.FAILED, payload={"sem": "evento"}, meta={}))

    done = await module.webhook_service.retry_failed(db)
    record = await db.scalar(select(WebhookEvent).where(WebhookEvent.external_event_id == "y"))

    assert done == []
    assert record.status == WebhookEventStatus.IGNORED


async def test_a_failure_that_repeats_on_the_retry_stays_failed(db, tenant, member, monkeypatch):
    from services import webhook as module

    integration, _ = await wire(db, tenant, member)
    call = module.InboundCall(method="POST", headers={"content-type": "application/json"}, body=json.dumps(event("INITIAL_PURCHASE", member)).encode())

    async def explode(*args, **kwargs):
        raise RuntimeError("keeps falling over")

    monkeypatch.setattr(module.PROVIDERS[Provider.REVENUECAT], "state_from_query", explode)

    with pytest.raises(RuntimeError):
        await module.webhook_service.ingest(db, integration, call)

    done = await module.webhook_service.retry_failed(db)
    record = await db.scalar(select(WebhookEvent))

    assert done == []
    assert record.status == WebhookEventStatus.FAILED
    assert record.attempts == 2


async def test_one_event_failing_again_does_not_stop_the_retry_of_the_next(db, tenant, member, monkeypatch):
    """The pass recovers a queue and not a row, so the second stuck event is reached even after the first falls over again."""
    from services import webhook as module

    integration, _ = await wire(db, tenant, member)

    for external in ("first", "second"):
        await save(db, WebhookEvent(tenant_id=tenant.id, integration_id=integration.id, external_event_id=external, payload_hash=external, status=WebhookEventStatus.FAILED, payload=event("INITIAL_PURCHASE", member, id=external), meta={}))

    async def explode_once(*args, **kwargs):
        monkeypatch.undo()
        monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", answering())

        raise RuntimeError("fell over")

    monkeypatch.setattr(module.PROVIDERS[Provider.REVENUECAT], "state_from_query", explode_once)

    done = await module.webhook_service.retry_failed(db)

    assert [record.external_event_id for record in done] == ["second"]


async def test_the_admin_reads_the_address_of_an_integration(client, db, tenant, admin_headers):
    integration = await make_integration(db, tenant, provider=Provider.REVENUECAT)

    response = await client.get(f"/api/integrations/{integration.id}", headers=admin_headers)

    assert response.json()["webhookKey"] == integration.webhook_key


async def test_an_integration_created_by_the_admin_is_born_with_its_own_address(client, db, tenant, admin_headers):
    payload = {"tenantId": tenant.id, "provider": Provider.REVENUECAT}

    first = await client.post("/api/integrations", json=payload, headers=admin_headers)
    second = await client.post("/api/integrations", json=payload | {"provider": Provider.STRIPE}, headers=admin_headers)

    assert first.json()["webhookKey"]
    assert first.json()["webhookKey"] != second.json()["webhookKey"]


async def test_the_address_is_not_something_the_admin_can_write(client, db, tenant, admin_headers):
    response = await client.post("/api/integrations", json={"tenantId": tenant.id, "provider": Provider.REVENUECAT, "webhookKey": "escolhida-a-mao"}, headers=admin_headers)

    assert response.status_code == 422


async def test_the_provider_contract_says_what_a_gateway_has_to_answer(db):
    """A gateway that skips one of them fails where it is written, not deep inside a pass."""
    from services.gateway import InboundCall, PaymentProvider

    gateway = PaymentProvider()
    call = InboundCall(method="POST")

    assert gateway.queryable is False
    assert gateway.event_stated is False

    with pytest.raises(NotImplementedError):
        gateway.authenticate(None, call, "")

    with pytest.raises(NotImplementedError):
        await gateway.read(None, call, None)

    with pytest.raises(NotImplementedError):
        await gateway.state_from_query("k", "t", None)


async def test_an_event_a_dead_node_left_mid_flight_is_picked_up(db, tenant, member, monkeypatch):
    """A deploy between the mark and the reading leaves a row nobody would ever look at again."""
    from datetime import timedelta

    from services import webhook as module

    integration, _ = await wire(db, tenant, member)

    stuck = await save(db, WebhookEvent(tenant_id=tenant.id, integration_id=integration.id, external_event_id="evt-parado", payload_hash="h", status=WebhookEventStatus.PROCESSING, payload=event("INITIAL_PURCHASE", member), meta={}))
    stuck.updated_at = now() - timedelta(hours=2)
    await db.commit()

    done = await module.webhook_service.retry_failed(db)
    await db.refresh(stuck)

    assert len(done) == 1
    assert stuck.status == WebhookEventStatus.COMPLETED


async def test_an_event_another_node_is_running_right_now_is_left_alone(db, tenant, member):
    """A live node finishes in seconds, so a fresh processing row belongs to somebody else."""
    from services import webhook as module

    integration, _ = await wire(db, tenant, member)

    await save(db, WebhookEvent(tenant_id=tenant.id, integration_id=integration.id, external_event_id="evt-vivo", payload_hash="h", status=WebhookEventStatus.PROCESSING, payload=event("INITIAL_PURCHASE", member), meta={}))

    assert await module.webhook_service.retry_failed(db) == []


@pytest.mark.parametrize("stamp", ["not-a-number", "17.5", 10**25])
async def test_a_stamp_nothing_can_read_never_costs_the_whole_notice(client, db, tenant, member, stamp):
    """The event is read before it is written down, so a raise here loses what arrived and the gateway retries into nothing."""
    integration, _ = await wire(db, tenant, member)

    body = event("INITIAL_PURCHASE", member)
    body["event"]["event_timestamp_ms"] = stamp

    answer = await client.post(f"/api/webhooks/{integration.webhook_key}", json=body)

    assert answer.json()["status"] == WebhookEventStatus.COMPLETED
    assert (await db.scalar(select(WebhookEvent))).occurred_at is None


@pytest.mark.parametrize("stamp", ["not-a-date", "2026-13-45T00:00:00Z", "yesterday"])
async def test_a_date_the_provider_answered_that_nothing_can_read_is_read_as_none(stamp):
    """The subscriber endpoint answers ISO 8601, and one that is not still has to leave the rest of the answer readable."""
    from enums.integration import Provider
    from services.gateway import PROVIDERS

    assert PROVIDERS[Provider.REVENUECAT].instant(stamp) is None
    assert PROVIDERS[Provider.REVENUECAT].instant("2026-08-19T12:00:00Z") is not None


async def test_a_signature_somebody_kept_is_refused_however_right_it_is(client, db, tenant, member):
    """RevenueCat signs each delivery afresh, retries included, so a stamp older than the window is a call somebody captured and sent again."""
    integration, _ = await wire(db, tenant, member, revenuecat_webhook_secret_encrypted=encrypt("assinatura-secreta"))
    body = json.dumps(event("INITIAL_PURCHASE", member)).encode()
    stale = int((now() - TOLERANCE - timedelta(seconds=10)).timestamp())
    signature = hmac.new(b"assinatura-secreta", f"{stale}.".encode() + body, hashlib.sha256).hexdigest()

    kept = await client.post(f"/api/webhooks/{integration.webhook_key}", content=body, headers={"Content-Type": "application/json", "X-RevenueCat-Webhook-Signature": f"t={stale},v1={signature}"})

    assert kept.status_code == 401
