"""A gateway is a class, and these prove the contract fits the shapes the real ones have."""

import hashlib
import hmac
import json
from datetime import timedelta

import httpx
import pytest
from sqlalchemy import select

from enums.integration import Environment, Provider
from enums.subscription import BenefitCadence, BenefitType, SubscriptionStatus
from helpers.dates import now
from helpers.security import create_token
from models.integration import ExternalProduct, WebhookEvent
from models.subscription import Subscription
from services import gateway as module
from services.gateway import API_KEY, WEBHOOK_SECRET, Credential, PaymentProvider, ProviderEvent, ProviderPurchase
from tests.factories import make_benefit, make_entitlement, make_integration, make_plan, make_plan_entitlement, make_product, save


class MercadoPagoShaped(PaymentProvider):
    """Its notice carries only a resource id, so who bought and what they hold are both learned by asking."""

    event_stated = True
    API = "https://api.mercadopago.com"
    credentials = (Credential("revenuecat_api_key", "Access token", "the double borrows a column, because only revenuecat has one of its own", API_KEY), Credential("revenuecat_webhook_secret", "Assinatura secreta", "the double borrows a column", WEBHOOK_SECRET))

    def authenticate(self, integration, call, secret):
        signature = call.headers.get("x-signature", "")
        parts = dict(piece.strip().split("=", 1) for piece in signature.split(",") if "=" in piece)
        manifest = f"id:{call.query.get('data.id')};request-id:{call.headers.get('x-request-id')};ts:{parts.get('ts')};"
        expected = hmac.new(b"segredo", manifest.encode(), hashlib.sha256).hexdigest()

        if not hmac.compare_digest(expected, parts.get("v1", "")):
            raise module.AuthenticationError("error.webhook-signature-invalid")

    async def read(self, integration, call, client):
        body = call.data()

        if body.get("type") != "payment":
            return None

        answer = await client.get(f"{self.API}/v1/payments/{body['data']['id']}")
        payment = answer.json()

        return ProviderEvent(
            external_event_id=str(body["id"]),
            event_type=str(body.get("action")),
            account_token=payment["external_reference"],
            product_reference=payment["metadata"]["plan"],
            state=(ProviderPurchase(external_id=str(payment["id"]), product_reference=payment["metadata"]["plan"], purchased_at=now(), period_ends_at=now() + timedelta(days=30), environment=Environment.PRODUCTION if payment["live_mode"] else Environment.SANDBOX),),
        )


class StripeShaped(PaymentProvider):
    """Its notice carries the object itself, so nothing has to be asked."""

    event_stated = True
    credentials = (Credential("revenuecat_api_key", "Secret key", "the double borrows a column", API_KEY), Credential("revenuecat_webhook_secret", "Signing secret", "the double borrows a column", WEBHOOK_SECRET))

    def authenticate(self, integration, call, secret):
        parts = dict(piece.split("=", 1) for piece in call.headers.get("stripe-signature", "").split(",") if "=" in piece)
        expected = hmac.new(b"segredo", f"{parts.get('t')}.".encode() + call.body, hashlib.sha256).hexdigest()

        if not hmac.compare_digest(expected, parts.get("v1", "")):
            raise module.AuthenticationError("error.webhook-signature-invalid")

    async def read(self, integration, call, client):
        body = call.data()
        obj = body["data"]["object"]

        return ProviderEvent(
            external_event_id=body["id"],
            event_type=body["type"],
            account_token=obj["metadata"]["account_token"],
            product_reference=obj["items"]["data"][0]["price"]["id"],
            state=(ProviderPurchase(external_id=obj["id"], product_reference=obj["items"]["data"][0]["price"]["id"], purchased_at=now(), period_ends_at=now() + timedelta(days=30)),),
        )


async def wire(db, tenant, provider: Provider, external: str):
    integration = await make_integration(db, tenant, provider=provider)
    plan = await make_plan(db, tenant, code=f"plan-{provider}", name=f"Plan {provider}")

    await save(db, ExternalProduct(integration_id=integration.id, plan_id=plan.id, external_id=external, active=True, meta={}))

    return integration, plan


def mercado_pago_signature(data_id: str, request_id: str, stamp: str) -> str:
    manifest = f"id:{data_id};request-id:{request_id};ts:{stamp};"

    return f"ts={stamp},v1={hmac.new(b'segredo', manifest.encode(), hashlib.sha256).hexdigest()}"


async def test_a_gateway_whose_notice_carries_only_an_id_resolves_the_account_by_asking(monkeypatch, db, tenant, member, client):
    integration, plan = await wire(db, tenant, Provider.REVENUECAT, "premium")

    async def answering(self, request):
        return httpx.Response(200, json={"id": 987, "external_reference": member.token, "live_mode": True, "metadata": {"plan": "premium"}})

    monkeypatch.setitem(module.PROVIDERS, Provider.REVENUECAT, MercadoPagoShaped())
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", answering)

    body = json.dumps({"id": 111, "type": "payment", "action": "payment.created", "data": {"id": "987"}}).encode()
    headers = {"content-type": "application/json", "x-request-id": "req-1", "x-signature": mercado_pago_signature("987", "req-1", "1700000000")}

    response = await client.post(f"/api/webhooks/{integration.webhook_key}?data.id=987", content=body, headers=headers)
    subscription = await db.scalar(select(Subscription))

    assert response.json()["status"] == "completed"
    assert subscription.plan_id == plan.id
    assert subscription.status == SubscriptionStatus.ACTIVE
    assert subscription.external_id == "987"


async def test_a_gateway_whose_notice_carries_the_object_needs_no_call_at_all(monkeypatch, db, tenant, member, client):
    integration, plan = await wire(db, tenant, Provider.STRIPE, "price_premium")

    async def refuse(self, request):
        raise AssertionError("a gateway whose notice carries the object was asked something")

    monkeypatch.setitem(module.PROVIDERS, Provider.STRIPE, StripeShaped())
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", refuse)

    body = json.dumps({"id": "evt_1", "type": "customer.subscription.updated", "data": {"object": {"id": "sub_1", "metadata": {"account_token": member.token}, "items": {"data": [{"price": {"id": "price_premium"}}]}}}}).encode()
    signature = f"t=1700000000,v1={hmac.new(b'segredo', b'1700000000.' + body, hashlib.sha256).hexdigest()}"

    response = await client.post(f"/api/webhooks/{integration.webhook_key}", content=body, headers={"content-type": "application/json", "stripe-signature": signature})
    subscription = await db.scalar(select(Subscription))

    assert response.json()["status"] == "completed"
    assert subscription.plan_id == plan.id
    assert subscription.external_id == "sub_1"


async def test_a_notice_signed_with_the_wrong_secret_never_reaches_the_payload(monkeypatch, db, tenant, client):
    integration, _ = await wire(db, tenant, Provider.REVENUECAT, "premium")

    async def refuse(self, request):
        raise AssertionError("a call that failed to authenticate reached the gateway")

    monkeypatch.setitem(module.PROVIDERS, Provider.REVENUECAT, MercadoPagoShaped())
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", refuse)

    body = json.dumps({"id": 111, "type": "payment", "data": {"id": "987"}}).encode()
    headers = {"content-type": "application/json", "x-request-id": "req-1", "x-signature": "ts=1,v1=" + "0" * 64}

    response = await client.post(f"/api/webhooks/{integration.webhook_key}?data.id=987", content=body, headers=headers)

    assert response.status_code == 401
    assert await db.scalar(select(Subscription)) is None


async def test_a_notice_about_something_this_gateway_does_not_report_is_kept_unread(monkeypatch, db, tenant, client):
    integration, _ = await wire(db, tenant, Provider.REVENUECAT, "premium")

    monkeypatch.setitem(module.PROVIDERS, Provider.REVENUECAT, MercadoPagoShaped())

    body = json.dumps({"id": 222, "type": "plan", "data": {"id": "1"}}).encode()
    headers = {"content-type": "application/json", "x-request-id": "req-2", "x-signature": mercado_pago_signature("1", "req-2", "1700000000")}

    response = await client.post(f"/api/webhooks/{integration.webhook_key}?data.id=1", content=body, headers=headers)
    stored = await db.scalar(select(WebhookEvent))

    assert response.json()["status"] == "ignored"
    assert stored.error_code == "unread"
    assert stored.payload["type"] == "plan"


async def test_two_gateways_of_the_same_tenant_hold_their_own_subscriptions(monkeypatch, db, tenant, member, client):
    """A queryable gateway and one that only tells live side by side, and neither reads the other's rows."""
    stripe, stripe_plan = await wire(db, tenant, Provider.STRIPE, "price_premium")

    monkeypatch.setitem(module.PROVIDERS, Provider.STRIPE, StripeShaped())

    body = json.dumps({"id": "evt_2", "type": "customer.subscription.updated", "data": {"object": {"id": "sub_2", "metadata": {"account_token": member.token}, "items": {"data": [{"price": {"id": "price_premium"}}]}}}}).encode()
    signature = f"t=1700000000,v1={hmac.new(b'segredo', b'1700000000.' + body, hashlib.sha256).hexdigest()}"

    await client.post(f"/api/webhooks/{stripe.webhook_key}", content=body, headers={"content-type": "application/json", "stripe-signature": signature})

    revenuecat, revenuecat_plan = await wire(db, tenant, Provider.REVENUECAT, "mensal")

    async def answering(self, request):
        return httpx.Response(200, json={"subscriber": {"subscriptions": {"mensal": {"expires_date": (now() + timedelta(days=30)).isoformat().replace("+00:00", "Z"), "purchase_date": now().isoformat().replace("+00:00", "Z"), "store_transaction_id": "txn-rc", "period_type": "NORMAL", "is_sandbox": False}}}})

    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", answering)

    from helpers.security import encrypt
    from services.integration import integration_service

    revenuecat.revenuecat_api_key_encrypted = encrypt("sk-revenuecat")
    await db.commit()

    from services.reconciliation import reconciliation_service

    await reconciliation_service.reconcile_account(db, revenuecat, member)

    rows = {s.integration_id: s for s in (await db.execute(select(Subscription))).scalars()}

    assert integration_service is not None
    assert len(rows) == 2
    assert rows[stripe.id].plan_id == stripe_plan.id
    assert rows[revenuecat.id].plan_id == revenuecat_plan.id


async def test_a_purchase_from_a_gateway_nobody_wrote_yet_reaches_the_account(monkeypatch, db, tenant, member, client):
    """The seam ends at the reconciliation: everything past it decides by the plan, and never by which gateway paid."""
    product = await make_product(db, tenant, name="The Handbook")

    integration = await make_integration(db, tenant, provider=Provider.STRIPE)
    plan = await make_plan(db, tenant, code="plan-new", name="New plan")
    entitlement = await make_entitlement(db, tenant, code="membership")
    await make_plan_entitlement(db, plan, entitlement)
    await make_benefit(db, entitlement, type=BenefitType.ACCESS, target="access", cadence=BenefitCadence.ON_ACTIVATION, grant_on_activation=True)
    await make_benefit(db, entitlement, type=BenefitType.PRODUCT, target="handbook", product_id=product.id, cadence=BenefitCadence.ON_ACTIVATION, grant_on_activation=True)
    await save(db, ExternalProduct(integration_id=integration.id, plan_id=plan.id, external_id="price_new", active=True, meta={}))

    session = {"Authorization": f"Bearer {create_token(member.token, member.role, member.session_epoch)}"}

    assert (await client.get("/api/account/products", headers=session)).json()["items"] == []

    monkeypatch.setitem(module.PROVIDERS, Provider.STRIPE, StripeShaped())

    body = json.dumps({"id": "evt_new", "type": "customer.subscription.updated", "data": {"object": {"id": "sub_new", "metadata": {"account_token": member.token}, "items": {"data": [{"price": {"id": "price_new"}}]}}}}).encode()
    signature = f"t=1700000000,v1={hmac.new(b'segredo', b'1700000000.' + body, hashlib.sha256).hexdigest()}"

    await client.post(f"/api/webhooks/{integration.webhook_key}", content=body, headers={"content-type": "application/json", "stripe-signature": signature})

    owned = await client.get("/api/account/products", headers=session)
    rights = await client.get("/api/account/entitlements", headers=session)

    assert [item["name"] for item in owned.json()["items"]] == ["The Handbook"]
    assert [right["code"] for right in rights.json()["items"]] == ["membership"]


def test_every_gateway_names_its_own_keys_and_asks_only_for_places_that_exist():
    """A generic label sends an operator looking in the panel for a field that is not called that."""
    from models.integration import Integration
    from schemas.integration import IntegrationCreate
    from services.gateway import PROVIDERS

    for provider, gateway in PROVIDERS.items():
        assert gateway.credentials, f"{provider} does not say what an operator has to paste"
        assert [credential.field for credential in gateway.credentials if credential.role], f"{provider} says what to paste and never what any of it is for"

        for credential in gateway.credentials:
            assert hasattr(Integration, f"{credential.field}_encrypted"), f"{provider} asks for {credential.field}, which the integration has nowhere to keep"
            assert credential.field in IntegrationCreate.model_fields, f"{provider} asks for {credential.field}, which the api does not accept"
            assert credential.field.startswith(provider.value), f"{provider} keeps {credential.field}, which is not named after itself"
            assert not credential.label.startswith("field."), f"{provider} names {credential.field} with a translation key instead of what its panel calls it"


async def test_the_meta_publishes_what_each_gateway_asks_for(client):
    from services.gateway import PROVIDERS

    published = (await client.get("/api/meta")).json()["providerCredentials"]

    for provider, gateway in PROVIDERS.items():
        asked = [{"field": credential.field, "label": credential.label, "hint": credential.hint} for credential in gateway.credentials]

        assert published[provider.value] == asked


def test_a_gateway_naming_two_credentials_for_one_part_is_refused():
    """The part decides which key is read, so two answers for it is one of them chosen by order."""
    from services.gateway import API_KEY, Credential, PaymentProvider, ProviderEvent

    with pytest.raises(TypeError, match="same part"):

        class Twofold(PaymentProvider):
            def authenticate(self, integration, call, secret):
                return None

            event_stated = True
            credentials = (Credential("revenuecat_api_key", "One", "the double borrows a column", API_KEY), Credential("revenuecat_webhook_secret", "Another", "the double borrows a column", API_KEY))

            async def read(self, integration, call, client):
                return ProviderEvent(external_event_id="x", event_type="y")
