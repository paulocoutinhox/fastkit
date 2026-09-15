from datetime import timedelta

import httpx
import pytest
from sqlalchemy import func, select

import jobs.subscription  # noqa: F401
from enums.integration import Environment, Provider
from enums.subscription import BenefitStatus, BenefitType, SubscriptionStatus
from enums.system_log import LogCategory
from enums.user import UserRole, UserStatus
from helpers.dates import now
from helpers.db import AsyncSessionLocal
from helpers.scheduler import app as tasks
from helpers.security import encrypt
from models.commerce import UserProduct
from models.integration import ExternalProduct
from models.subscription import Subscription, SubscriptionBenefit, UserEntitlement
from models.system_log import SystemLog
from models.user import User
from services import reconciliation
from services.gateway import PROVIDERS
from services.reconciliation import COOLDOWN, PACE, SWEEP_LIMIT, SWEEP_WINDOW, reconciliation_service
from services.user import user_service
from tests.factories import make_benefit, make_entitlement, make_integration, make_plan, make_plan_entitlement, make_product, make_subscription, save

SECRET = "sk-revenuecat"


def instant(days: float) -> str:
    return (now() + timedelta(days=days)).isoformat().replace("+00:00", "Z")


def recurring(**overrides) -> dict:
    return {"expires_date": instant(30), "period_type": "NORMAL", "store": "APP_STORE", "ownership_type": "PURCHASED", "is_sandbox": False, "store_transaction_id": "txn-1", "purchase_date": instant(-1)} | overrides


def once(**overrides) -> dict:
    return {"id": "once-1", "purchase_date": instant(-1), "store": "APP_STORE", "is_sandbox": False} | overrides


def answering(subscriptions: dict | None = None, non_subscriptions: dict | None = None, status: int = 200, headers: dict | None = None):
    async def responder(self, request):
        return httpx.Response(status, json={"subscriber": {"subscriptions": subscriptions or {}, "non_subscriptions": non_subscriptions or {}}}, headers=headers or {})

    return responder


def refusing(error: Exception):
    async def responder(self, request):
        raise error

    return responder


@pytest.fixture(autouse=True)
def unpaced(monkeypatch):
    """The sweep paces itself against the gateway, and a test is about which accounts it asks about and never about the clock."""

    async def instantly(seconds):
        return None

    monkeypatch.setattr(reconciliation, "asyncio", type("clock", (), {"sleep": staticmethod(instantly)}))


@pytest.fixture
async def wired(db, tenant, member):
    integration = await make_integration(db, tenant, provider=Provider.REVENUECAT, revenuecat_api_key_encrypted=encrypt(SECRET))
    plan = await make_plan(db, tenant)

    await save(db, ExternalProduct(integration_id=integration.id, plan_id=plan.id, external_id="mensal", active=True, meta={}))

    return {"integration": integration, "plan": plan, "user": member}


async def mirror(monkeypatch, db, wired, responder) -> int:
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", responder)

    return await reconciliation_service.reconcile_account(db, wired["integration"], wired["user"])


async def only_subscription(db) -> Subscription | None:
    return await db.scalar(select(Subscription))


async def warnings_of(db) -> list[str]:
    return list((await db.execute(select(SystemLog.description).where(SystemLog.category == LogCategory.PURCHASE))).scalars())


async def test_a_purchase_the_provider_holds_and_we_never_heard_of_is_opened_and_delivered(monkeypatch, db, wired):
    changes = await mirror(monkeypatch, db, wired, answering({"mensal": recurring()}))
    subscription = await only_subscription(db)

    assert changes == 1
    assert subscription.status == SubscriptionStatus.ACTIVE
    assert subscription.plan_id == wired["plan"].id
    assert subscription.external_id == "txn-1"


async def test_two_sides_that_already_agree_change_nothing(monkeypatch, db, wired):
    same = recurring()

    await mirror(monkeypatch, db, wired, answering({"mensal": same}))
    changes = await mirror(monkeypatch, db, wired, answering({"mensal": same}))

    assert changes == 0
    assert len((await db.execute(select(Subscription))).scalars().all()) == 1


async def test_a_free_trial_is_mirrored_as_one(monkeypatch, db, wired):
    await mirror(monkeypatch, db, wired, answering({"mensal": recurring(period_type="TRIAL")}))
    subscription = await only_subscription(db)

    assert subscription.status == SubscriptionStatus.TRIALING
    assert subscription.trial_ends_at is not None


async def test_an_introductory_price_is_mirrored_as_a_trial_too(monkeypatch, db, wired):
    """Both are a period the reader is not paying full price for, and both end into a normal one."""
    await mirror(monkeypatch, db, wired, answering({"mensal": recurring(period_type="INTRO")}))

    assert (await only_subscription(db)).status == SubscriptionStatus.TRIALING


async def test_a_promotional_period_is_a_normal_active_one(monkeypatch, db, wired):
    await mirror(monkeypatch, db, wired, answering({"mensal": recurring(period_type="PROMOTIONAL")}))

    assert (await only_subscription(db)).status == SubscriptionStatus.ACTIVE


async def test_a_billing_issue_is_mirrored_as_the_grace_the_provider_named(monkeypatch, db, wired):
    await mirror(monkeypatch, db, wired, answering({"mensal": recurring(grace_period_expires_date=instant(16), billing_issues_detected_at=instant(0))}))
    subscription = await only_subscription(db)

    assert subscription.status == SubscriptionStatus.GRACE_PERIOD
    assert subscription.access_until == subscription.grace_until


async def test_a_paused_subscription_stops_delivering_and_keeps_the_date_it_resumes(monkeypatch, db, wired):
    await mirror(monkeypatch, db, wired, answering({"mensal": recurring(auto_resume_date=instant(60))}))
    subscription = await only_subscription(db)

    assert subscription.status == SubscriptionStatus.SUSPENDED
    assert subscription.benefit_status == BenefitStatus.PAUSED


async def test_a_cancellation_keeps_the_access_that_was_paid_for(monkeypatch, db, wired):
    await mirror(monkeypatch, db, wired, answering({"mensal": recurring(unsubscribe_detected_at=instant(0))}))
    subscription = await only_subscription(db)

    assert subscription.cancel_at_period_end is True
    assert subscription.canceled_at is not None
    assert subscription.status == SubscriptionStatus.ACTIVE


async def test_a_refund_takes_the_access_away_now(monkeypatch, db, wired):
    await mirror(monkeypatch, db, wired, answering({"mensal": recurring()}))
    changes = await mirror(monkeypatch, db, wired, answering({"mensal": recurring(refunded_at=instant(0))}))

    assert changes == 1
    assert (await only_subscription(db)).status == SubscriptionStatus.REVOKED


async def test_a_period_the_provider_says_has_ended_expires_here(monkeypatch, db, wired):
    await mirror(monkeypatch, db, wired, answering({"mensal": recurring()}))
    changes = await mirror(monkeypatch, db, wired, answering({"mensal": recurring(expires_date=instant(-1))}))
    subscription = await only_subscription(db)

    assert changes == 1
    assert subscription.status == SubscriptionStatus.EXPIRED
    assert subscription.benefit_status == BenefitStatus.ENDED


async def test_a_purchase_shared_by_a_family_is_mirrored_saying_so(monkeypatch, db, wired):
    """The reader did not buy it and still holds it, and the support has to be able to see which of the two it is."""
    await mirror(monkeypatch, db, wired, answering({"mensal": recurring(ownership_type="FAMILY_SHARED")}))
    subscription = await only_subscription(db)

    assert subscription.status == SubscriptionStatus.ACTIVE
    assert subscription.meta["provider"]["ownership"] == "FAMILY_SHARED"
    assert subscription.meta["provider"]["store"] == "APP_STORE"


async def test_a_purchase_that_never_renews_grants_access_that_never_ends(monkeypatch, db, wired):
    """A one time purchase carries no period, so nothing about it can be past and nothing expires it."""
    await save(db, ExternalProduct(integration_id=wired["integration"].id, plan_id=wired["plan"].id, external_id="vitalicio", active=True, meta={}))

    changes = await mirror(monkeypatch, db, wired, answering(non_subscriptions={"vitalicio": [once()]}))
    subscription = await only_subscription(db)

    assert changes == 1
    assert subscription.status == SubscriptionStatus.ACTIVE
    assert subscription.access_until is None
    assert subscription.external_id == "once-1"
    assert subscription.meta["provider"]["recurring"] is False


async def test_a_sandbox_purchase_is_mirrored_and_delivers_like_any_other(monkeypatch, db, wired):
    """A test purchase has to work end to end, or there is no way to test the thing that takes money."""
    changes = await mirror(monkeypatch, db, wired, answering({"mensal": recurring(is_sandbox=True)}))
    subscription = await only_subscription(db)

    assert changes == 1
    assert subscription.status == SubscriptionStatus.ACTIVE
    assert subscription.environment == Environment.SANDBOX


async def test_sandbox_and_production_live_side_by_side_on_one_account(monkeypatch, db, wired):
    await save(db, ExternalProduct(integration_id=wired["integration"].id, plan_id=wired["plan"].id, external_id="anual", active=True, meta={}))
    await mirror(monkeypatch, db, wired, answering({"mensal": recurring(), "anual": recurring(store_transaction_id="txn-2", is_sandbox=True)}))

    environments = {s.external_id: s.environment for s in (await db.execute(select(Subscription))).scalars()}

    assert environments == {"txn-1": Environment.PRODUCTION, "txn-2": Environment.SANDBOX}


async def test_a_product_change_closes_the_old_one_and_opens_the_new(monkeypatch, db, tenant, wired):
    other = await make_plan(db, tenant, code="anual", name="Anual")

    await save(db, ExternalProduct(integration_id=wired["integration"].id, plan_id=other.id, external_id="anual", active=True, meta={}))
    await mirror(monkeypatch, db, wired, answering({"mensal": recurring()}))
    await mirror(monkeypatch, db, wired, answering({"anual": recurring(store_transaction_id="txn-2")}))

    subscriptions = {s.external_id: s for s in (await db.execute(select(Subscription))).scalars()}

    assert subscriptions["txn-1"].status == SubscriptionStatus.EXPIRED
    assert subscriptions["txn-2"].plan_id == other.id


async def test_what_the_provider_stopped_holding_stops_being_ours(monkeypatch, db, wired):
    """A purchase the provider stopped listing is one this account no longer holds, and no event has to say so."""
    await mirror(monkeypatch, db, wired, answering({"mensal": recurring()}))
    changes = await mirror(monkeypatch, db, wired, answering({}))

    assert changes == 1
    assert (await only_subscription(db)).status == SubscriptionStatus.EXPIRED
    assert any("no longer holds it" in warning for warning in await warnings_of(db))


async def test_a_product_nothing_here_maps_is_reported_and_not_opened(monkeypatch, db, wired):
    changes = await mirror(monkeypatch, db, wired, answering({"nao-mapeado": recurring()}))

    assert changes == 0
    assert await only_subscription(db) is None
    assert any("nothing maps it" in warning for warning in await warnings_of(db))


async def test_a_purchase_already_over_when_it_is_first_seen_is_not_opened(monkeypatch, db, wired):
    changes = await mirror(monkeypatch, db, wired, answering({"mensal": recurring(expires_date=instant(-5))}))

    assert changes == 0
    assert await only_subscription(db) is None


async def test_a_pause_the_provider_asked_for_changes_nothing(monkeypatch, db, wired):
    changes = await mirror(monkeypatch, db, wired, answering({"mensal": recurring()}, status=429, headers={"Retry-After": "1"}))

    assert changes == 0
    assert await only_subscription(db) is None


async def test_a_provider_that_did_not_answer_changes_nothing(monkeypatch, db, wired):
    await mirror(monkeypatch, db, wired, answering({"mensal": recurring()}))
    changes = await mirror(monkeypatch, db, wired, refusing(httpx.ConnectError("no network")))

    assert changes == 0
    assert (await only_subscription(db)).status == SubscriptionStatus.ACTIVE


async def test_an_answer_that_failed_changes_nothing(monkeypatch, db, wired):
    changes = await mirror(monkeypatch, db, wired, answering(status=500))

    assert changes == 0
    assert await only_subscription(db) is None


async def test_an_error_that_is_not_the_provider_failing_is_never_swallowed(monkeypatch, db, wired):
    """Catching everything would hide a bug of ours behind a message about the network."""

    def broken(self, subscription, purchase):
        raise TypeError("a bug of ours")

    monkeypatch.setattr(type(reconciliation_service), "carry", broken)

    with pytest.raises(TypeError):
        await mirror(monkeypatch, db, wired, answering({"mensal": recurring()}))


async def test_an_integration_with_no_key_says_so_instead_of_answering_nothing(monkeypatch, db, tenant, member):
    """Answering zero would read as a purchase that was handled, and the operator would never learn the key is missing."""
    from services.reconciliation import Unreadable

    integration = await make_integration(db, tenant, provider=Provider.REVENUECAT, revenuecat_api_key_encrypted=None)

    async def refuse(self, request):
        raise AssertionError("the provider was called without a key")

    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", refuse)

    with pytest.raises(Unreadable):
        await reconciliation_service.reconcile_account(db, integration, member)


async def test_a_pass_skips_what_it_cannot_ask_and_keeps_going(monkeypatch, db, tenant, member):
    """One integration missing its key is reported and never stops the pass."""
    integration = await make_integration(db, tenant, provider=Provider.REVENUECAT, revenuecat_api_key_encrypted=None)
    plan = await make_plan(db, tenant)
    product = await save(db, ExternalProduct(integration_id=integration.id, plan_id=plan.id, external_id="mensal", active=True, meta={}))

    await save(db, Subscription(tenant_id=tenant.id, user_id=member.id, plan_id=plan.id, integration_id=integration.id, external_product_id=product.id, external_id="txn-mudo", status=SubscriptionStatus.ACTIVE, access_until=now() - timedelta(days=1), meta={}))

    async def refuse(self, request):
        raise AssertionError("a provider with no key was called")

    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", refuse)

    assert await reconciliation_service.reconcile_stale(db) == 0


async def test_the_client_asks_the_address_the_documentation_names(monkeypatch, db, wired):
    """The token goes in the path and the key in the header, and no platform header is sent on an informational read."""
    seen = {}

    async def responder(self, request):
        seen["url"] = str(request.url)
        seen["authorization"] = request.headers.get("authorization")
        seen["platform"] = request.headers.get("x-platform")

        return httpx.Response(200, json={"subscriber": {"subscriptions": {}}})

    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", responder)

    async with httpx.AsyncClient() as client:
        await PROVIDERS[Provider.REVENUECAT].state_from_query(SECRET, wired["user"].token, client)

    assert seen["url"] == f"https://api.revenuecat.com/v1/subscribers/{wired['user'].token}"
    assert seen["authorization"] == f"Bearer {SECRET}"
    assert seen["platform"] is None


async def test_the_app_sees_a_purchase_the_moment_it_asks_for_it(monkeypatch, db, wired):
    """This is what makes a five minute sandbox subscription usable: nothing waits for a webhook and nothing waits for a cron."""
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", answering({"mensal": recurring()}))

    changes = await reconciliation_service.refresh(db, wired["user"])

    assert changes == 1
    assert (await only_subscription(db)).status == SubscriptionStatus.ACTIVE


async def test_a_client_in_a_loop_never_becomes_a_flood_of_calls(monkeypatch, db, wired):
    """The provider paces at one call a second, so a refresh asked twice in a row reads the second from what is already here."""
    calls = []

    async def counting(self, request):
        calls.append(1)

        return httpx.Response(200, json={"subscriber": {"subscriptions": {"mensal": recurring()}}})

    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", counting)

    await reconciliation_service.refresh(db, wired["user"])
    await reconciliation_service.refresh(db, wired["user"])

    assert len(calls) == 1


async def test_a_refresh_of_an_account_with_no_gateway_asks_nobody(monkeypatch, db, tenant, member):
    async def refuse(self, request):
        raise AssertionError("a provider was called with no integration wired")

    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", refuse)

    assert await reconciliation_service.refresh(db, member) == 0


async def test_a_first_purchase_is_protected_by_the_window_too(monkeypatch, db, wired):
    """The account holds nothing yet and that is exactly when an app asks the most, so the mark lives on the account."""
    calls = []

    async def counting(self, request):
        calls.append(1)

        return httpx.Response(200, json={"subscriber": {"subscriptions": {}}})

    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", counting)

    await reconciliation_service.refresh(db, wired["user"])
    await reconciliation_service.refresh(db, wired["user"])
    await reconciliation_service.refresh(db, wired["user"])

    assert len(calls) == 1


async def test_an_account_with_several_things_overdue_is_asked_about_once(monkeypatch, db, tenant, wired):
    """The question is about the account, so three stale subscriptions of one account are one call and not three."""
    other = await make_plan(db, tenant, code="anual", name="Anual")

    # Two subscriptions of one account are two products, because a store sells one of each at a time.
    for reference, external in (("anual", "txn-a"), ("anual-de-outro-grupo", "txn-b")):
        product = await save(db, ExternalProduct(integration_id=wired["integration"].id, plan_id=other.id, external_id=reference, active=True, meta={}))
        await save(db, Subscription(tenant_id=tenant.id, user_id=wired["user"].id, plan_id=other.id, integration_id=wired["integration"].id, external_product_id=product.id, external_id=external, status=SubscriptionStatus.ACTIVE, access_until=now() - timedelta(days=1), meta={}))

    calls = []

    async def counting(self, request):
        calls.append(1)

        return httpx.Response(200, json={"subscriber": {"subscriptions": {}}})

    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", counting)
    await reconciliation_service.reconcile_stale(db)

    assert len(calls) == 1


async def test_the_safety_net_asks_only_about_what_went_silent(monkeypatch, db, wired):
    """A healthy base costs no calls at all: what is running fine is never asked about."""
    calls = []

    async def counting(self, request):
        calls.append(1)

        return httpx.Response(200, json={"subscriber": {"subscriptions": {"mensal": recurring()}}})

    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", counting)

    await reconciliation_service.refresh(db, wired["user"])
    calls.clear()

    assert await reconciliation_service.reconcile_stale(db) == 0
    assert calls == []

    subscription = await only_subscription(db)
    subscription.access_until = now() - timedelta(minutes=1)
    await db.commit()

    await reconciliation_service.reconcile_stale(db)

    assert len(calls) == 1


async def test_a_subscription_of_a_gateway_that_cannot_be_asked_is_left_alone(monkeypatch, db, tenant, member):
    from services import gateway as module

    integration = await make_integration(db, tenant, provider=Provider.STRIPE, revenuecat_api_key_encrypted=encrypt(SECRET))
    plan = await make_plan(db, tenant)
    product = await save(db, ExternalProduct(integration_id=integration.id, plan_id=plan.id, external_id="mensal", active=True, meta={}))

    await save(db, Subscription(tenant_id=tenant.id, user_id=member.id, plan_id=plan.id, integration_id=integration.id, external_product_id=product.id, external_id="txn-x", status=SubscriptionStatus.ACTIVE, access_until=now() - timedelta(days=1), meta={}))

    async def refuse(self, request):
        raise AssertionError("a gateway with no reconciliation was asked")

    monkeypatch.setitem(module.PROVIDERS, Provider.STRIPE, module.PaymentProvider())
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", refuse)

    assert await reconciliation_service.reconcile_stale(db) == 0


async def test_a_gateway_that_only_tells_never_needs_to_be_asked(monkeypatch, db, tenant, member):
    """The state machine is ours, so a gateway with no query API reaches it through its own notice and nothing else changes."""
    from services import gateway as module
    from services.gateway import Credential, PaymentProvider, ProviderEvent, ProviderPurchase
    from services.webhook import webhook_service

    class Telling(PaymentProvider):
        event_stated = True
        credentials = (Credential("revenuecat_webhook_secret", "Signing secret", "the double borrows a column"),)

        def authenticate(self, integration, call, secret):
            return None

        async def read(self, integration, call, client):
            return ProviderEvent(external_event_id=call.data()["id"], event_type="paid", account_token=call.data()["payer"], state=(ProviderPurchase(external_id=call.data()["id"], product_reference="mensal", period_ends_at=now() + timedelta(days=30), purchased_at=now()),))

    integration = await make_integration(db, tenant, provider=Provider.STRIPE)
    plan = await make_plan(db, tenant)

    await save(db, ExternalProduct(integration_id=integration.id, plan_id=plan.id, external_id="mensal", active=True, meta={}))

    async def refuse(self, request):
        raise AssertionError("a gateway that only tells was asked")

    monkeypatch.setitem(module.PROVIDERS, Provider.STRIPE, Telling())
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", refuse)

    call = module.InboundCall(method="POST", headers={"content-type": "application/json"}, body=b'{"id": "mp-1", "payer": "' + member.token.encode() + b'"}')
    await webhook_service.ingest(db, integration, call)

    subscription = await only_subscription(db)

    assert subscription.status == SubscriptionStatus.ACTIVE
    assert subscription.plan_id == plan.id
    assert subscription.external_id == "mp-1"


async def test_the_metadata_an_operator_wrote_is_never_thrown_away(monkeypatch, db, wired):
    """The mirror adds what the provider says under its own key, and what a person put there stays."""
    await mirror(monkeypatch, db, wired, answering({"mensal": recurring()}))

    subscription = await only_subscription(db)
    subscription.meta = subscription.meta | {"nota": "cortesia do suporte"}
    await db.commit()

    await mirror(monkeypatch, db, wired, answering({"mensal": recurring(expires_date=instant(60))}))
    await db.refresh(subscription)

    assert subscription.meta["nota"] == "cortesia do suporte"
    assert subscription.meta["provider"]["store"] == "APP_STORE"


async def test_a_purchase_two_passes_open_at_once_is_written_once(monkeypatch, db, tenant, wired):
    """Two instances carrying the same cron tag run the same pass, and the transaction id is what settles it."""
    other = await make_plan(db, tenant, code="anual", name="Anual")
    product = await save(db, ExternalProduct(integration_id=wired["integration"].id, plan_id=other.id, external_id="anual", active=True, meta={}))

    await save(db, Subscription(tenant_id=tenant.id, user_id=wired["user"].id, plan_id=other.id, integration_id=wired["integration"].id, external_product_id=product.id, external_id="txn-1", status=SubscriptionStatus.ACTIVE, access_until=now() + timedelta(days=30), meta={}))

    changes = await mirror(monkeypatch, db, wired, answering({"mensal": recurring()}))
    rows = (await db.execute(select(Subscription).where(Subscription.external_id == "txn-1"))).scalars().all()

    assert len(rows) == 1
    assert changes == 1


async def test_a_lifetime_purchase_is_never_asked_about_again(monkeypatch, db, wired):
    """It has no deadline, so it can never be overdue: asking about it every pass would be the polling we do not do."""
    await save(db, ExternalProduct(integration_id=wired["integration"].id, plan_id=wired["plan"].id, external_id="vitalicio", active=True, meta={}))

    calls = []

    async def counting(self, request):
        calls.append(1)

        return httpx.Response(200, json={"subscriber": {"subscriptions": {}, "non_subscriptions": {"vitalicio": [once()]}}})

    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", counting)

    await reconciliation_service.reconcile_account(db, wired["integration"], wired["user"])
    calls.clear()

    assert await reconciliation_service.reconcile_stale(db) == 0
    assert calls == []


async def test_buying_the_same_lifetime_twice_is_still_one_thing_held(monkeypatch, db, wired):
    """The provider lists every purchase, and two of the same product would otherwise open and close a row on every pass."""
    await save(db, ExternalProduct(integration_id=wired["integration"].id, plan_id=wired["plan"].id, external_id="vitalicio", active=True, meta={}))

    twice = {"vitalicio": [once(), once(id="once-2", purchase_date=instant(0))]}

    await mirror(monkeypatch, db, wired, answering(non_subscriptions=twice))
    await mirror(monkeypatch, db, wired, answering(non_subscriptions=twice))

    rows = (await db.execute(select(Subscription))).scalars().all()

    assert len(rows) == 1
    assert rows[0].external_id == "once-2"
    assert rows[0].status == SubscriptionStatus.ACTIVE


async def test_a_refresh_of_a_gateway_with_no_key_is_reported_and_never_crashes_the_request(monkeypatch, db, tenant, member):
    """The app asked and there is nothing to answer with, so it is logged and the request still ends well."""
    await make_integration(db, tenant, provider=Provider.REVENUECAT, revenuecat_api_key_encrypted=None)

    async def refuse(self, request):
        raise AssertionError("a provider with no key was called")

    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", refuse)

    assert await reconciliation_service.refresh(db, member) == 0


async def test_a_renewal_the_clock_already_closed_is_still_found(monkeypatch, db, wired):
    """The clock expires what ran out and the provider is what knows it renewed, so what just closed is asked about once more."""
    await mirror(monkeypatch, db, wired, answering({"mensal": recurring()}))

    subscription = await only_subscription(db)
    subscription.status = SubscriptionStatus.EXPIRED
    subscription.expired_at = now()
    subscription.access_until = now()
    subscription.benefit_status = BenefitStatus.ENDED
    wired["user"].reconciled_at = None
    await db.commit()

    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", answering({"mensal": recurring(expires_date=instant(60))}))
    await reconciliation_service.reconcile_stale(db)
    await db.refresh(subscription)

    assert subscription.status == SubscriptionStatus.ACTIVE
    assert subscription.expired_at is None


async def test_a_subscription_closed_long_ago_is_left_alone(monkeypatch, db, wired):
    await mirror(monkeypatch, db, wired, answering({"mensal": recurring()}))

    subscription = await only_subscription(db)
    subscription.status = SubscriptionStatus.EXPIRED
    subscription.expired_at = now() - timedelta(days=30)
    subscription.access_until = now() - timedelta(days=30)
    await db.commit()

    calls = []

    async def counting(self, request):
        calls.append(1)

        return httpx.Response(200, json={"subscriber": {"subscriptions": {}}})

    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", counting)

    assert await reconciliation_service.reconcile_stale(db) == 0
    assert calls == []


async def test_a_gateway_that_only_tells_is_never_marked_as_asked(monkeypatch, db, tenant, member):
    """The mark says the provider was asked, and a gateway that only tells was never asked anything."""
    from services import gateway as module
    from services.gateway import Credential, PaymentProvider, ProviderEvent, ProviderPurchase
    from services.webhook import webhook_service

    class Telling(PaymentProvider):
        event_stated = True
        credentials = (Credential("revenuecat_webhook_secret", "Signing secret", "the double borrows a column"),)

        def authenticate(self, integration, call, secret):
            return None

        async def read(self, integration, call, client):
            return ProviderEvent(external_event_id="mp-1", event_type="paid", account_token=member.token, state=(ProviderPurchase(external_id="mp-1", product_reference="mensal", period_ends_at=now() + timedelta(days=30)),))

    integration = await make_integration(db, tenant, provider=Provider.STRIPE)
    plan = await make_plan(db, tenant)

    await save(db, ExternalProduct(integration_id=integration.id, plan_id=plan.id, external_id="mensal", active=True, meta={}))
    monkeypatch.setitem(module.PROVIDERS, Provider.STRIPE, Telling())

    await webhook_service.ingest(db, integration, module.InboundCall(method="POST", headers={"content-type": "application/json"}, body=b"{}"))
    await db.refresh(member)

    assert (await only_subscription(db)).status == SubscriptionStatus.ACTIVE
    assert member.reconciled_at is None


async def test_a_key_the_gateway_refuses_is_reported_and_not_treated_as_a_blip(monkeypatch, db, wired):
    """A rejected key is a configuration to fix, and waiting it out would leave every subscription silently unread."""
    from services.reconciliation import Unreadable

    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", answering(status=403))

    with pytest.raises(Unreadable):
        await reconciliation_service.reconcile_account(db, wired["integration"], wired["user"])

    assert any("refused the api key" in warning for warning in await warnings_of(db))


async def test_a_gateway_that_is_merely_down_is_waited_out(monkeypatch, db, wired):
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", answering(status=503))

    assert await reconciliation_service.reconcile_account(db, wired["integration"], wired["user"]) == 0


async def test_a_subscription_already_closed_is_not_closed_again(monkeypatch, db, wired):
    """The provider keeps listing a purchase whose period ended, so every pass would reclose it and push `expired_at` forward for good."""
    await mirror(monkeypatch, db, wired, answering({"mensal": recurring()}))

    ended = answering({"mensal": recurring(expires_date=instant(-1))})

    await mirror(monkeypatch, db, wired, ended)

    closed = await only_subscription(db)
    stamped = closed.expired_at

    assert closed.status == SubscriptionStatus.EXPIRED

    changes = await mirror(monkeypatch, db, wired, ended)

    assert changes == 0
    assert closed.expired_at == stamped
    assert len([line for line in await warnings_of(db) if "closed by a reconciliation" in line]) == 1


async def test_a_burst_of_refreshes_for_one_account_is_one_reading(monkeypatch, db, wired):
    """The app retries and comes back from the background, and the gateway is asked once and not once per call."""
    readings = []

    async def counting(self, request):
        readings.append(request.url.path)

        return httpx.Response(200, json={"subscriber": {"subscriptions": {"mensal": recurring()}, "non_subscriptions": {}}})

    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", counting)

    for _ in range(5):
        await reconciliation_service.refresh(db, wired["user"])

    assert len(readings) == 1


async def test_two_callers_racing_the_window_leave_one_of_them_reading(db, tenant, member):
    """The window is claimed in the database, so two processes never both decide they are the one asking."""
    async with AsyncSessionLocal() as first, AsyncSessionLocal() as second:
        mine = await first.get(User, member.id)
        theirs = await second.get(User, member.id)

        claims = [await reconciliation_service.claim_window(first, mine), await reconciliation_service.claim_window(second, theirs)]

    assert claims == [True, False]


async def test_the_window_opens_again_once_it_has_passed(db, member):
    assert await reconciliation_service.claim_window(db, member) is True

    member.reconciled_at = now() - COOLDOWN - timedelta(seconds=1)
    await db.commit()

    assert await reconciliation_service.claim_window(db, member) is True


async def test_a_subscription_that_changed_product_points_at_the_plan_that_was_bought(monkeypatch, db, tenant, wired):
    """An upgrade keeps the same purchase, so the row follows the product instead of a second subscription being opened."""
    annual = await make_plan(db, tenant, code="anual", name="Anual")
    await save(db, ExternalProduct(integration_id=wired["integration"].id, plan_id=annual.id, external_id="anual", active=True, meta={}))

    await mirror(monkeypatch, db, wired, answering({"mensal": recurring()}))

    subscription = await only_subscription(db)

    assert subscription.plan_id == wired["plan"].id

    await mirror(monkeypatch, db, wired, answering({"anual": recurring(store_transaction_id="txn-1")}))
    await db.refresh(subscription)

    assert subscription.plan_id == annual.id
    assert len((await db.execute(select(Subscription))).scalars().all()) == 1


async def test_moving_to_a_plan_that_starts_a_new_cycle_releases_the_one_that_was_running(monkeypatch, db, tenant, wired):
    """An upgrade is starting over rather than coming back, and the plan bought is what says so."""
    from enums.subscription import ResumeDeliveryPolicy

    annual = await make_plan(db, tenant, code="anual", name="Anual", resume_delivery_policy=ResumeDeliveryPolicy.NEW_CYCLE)
    await save(db, ExternalProduct(integration_id=wired["integration"].id, plan_id=annual.id, external_id="anual", active=True, meta={}))

    await mirror(monkeypatch, db, wired, answering({"mensal": recurring()}))

    subscription = await only_subscription(db)
    product = await make_product(db, tenant)

    await save(db, UserProduct(user_id=wired["user"].id, product_id=product.id, subscription_id=subscription.id, granted_at=now()))

    await mirror(monkeypatch, db, wired, answering({"anual": recurring(store_transaction_id="txn-1")}))
    await db.refresh(subscription)

    assert subscription.plan_id == annual.id

    # What was handed over stays, because what entered is the account's for good.
    assert await db.scalar(select(func.count()).select_from(UserProduct).where(UserProduct.user_id == wired["user"].id)) == 1


async def test_moving_to_a_plan_that_keeps_the_cycle_leaves_the_slots_where_they_are(monkeypatch, db, tenant, wired):
    """Paying a late bill and coming back is the common case, and it owes nothing new."""
    from enums.subscription import ResumeDeliveryPolicy

    annual = await make_plan(db, tenant, code="anual", name="Anual", resume_delivery_policy=ResumeDeliveryPolicy.SAME_CYCLE)
    await save(db, ExternalProduct(integration_id=wired["integration"].id, plan_id=annual.id, external_id="anual", active=True, meta={}))

    await mirror(monkeypatch, db, wired, answering({"mensal": recurring()}))
    await mirror(monkeypatch, db, wired, answering({"anual": recurring(store_transaction_id="txn-1")}))

    cycles = (await db.execute(select(SubscriptionBenefit.cycle))).scalars().all()

    assert all(cycle == 0 for cycle in cycles)


async def promising(db, tenant, wired) -> None:
    """The wired plan owes nothing on its own, and a subscription that owes nothing has no right to follow it."""
    entitlement = await make_entitlement(db, tenant)

    await make_plan_entitlement(db, wired["plan"], entitlement)
    await make_benefit(db, entitlement, type=BenefitType.ACCESS, target="access", quantity=1)


async def handed_over(monkeypatch, db, tenant, wired) -> tuple[User, Subscription, int]:
    """The store passes a receipt on only once nothing in it is active, so what arrives here is already over for the other account."""
    heir = await user_service.create(db, {"username": "heir", "email": "heir@acme.com", "password": "s3cret-password", "role": UserRole.NORMAL, "status": UserStatus.ACTIVE, "tenant_id": tenant.id})

    await mirror(monkeypatch, db, wired, answering({"mensal": recurring()}))

    subscription = await only_subscription(db)
    first_owner = subscription.user_id

    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", answering({"mensal": recurring()}))
    await reconciliation_service.reconcile_account(db, wired["integration"], heir)
    await db.refresh(subscription)

    return heir, subscription, first_owner


async def test_a_receipt_the_store_passed_on_follows_it_to_the_new_account(monkeypatch, db, tenant, wired):
    heir, subscription, first_owner = await handed_over(monkeypatch, db, tenant, wired)

    assert subscription.user_id == heir.id
    assert first_owner == wired["user"].id


async def test_a_receipt_that_moved_is_still_one_row(monkeypatch, db, tenant, wired):
    await handed_over(monkeypatch, db, tenant, wired)

    assert len((await db.execute(select(Subscription))).scalars().all()) == 1


async def test_the_right_follows_the_subscription_it_hangs_from(monkeypatch, db, tenant, wired):
    """A right is keyed by the subscription and never by the person, so it needs no moving of its own."""
    await promising(db, tenant, wired)

    _, subscription, _ = await handed_over(monkeypatch, db, tenant, wired)

    assert await db.scalar(select(UserEntitlement).where(UserEntitlement.subscription_id == subscription.id)) is not None


async def test_the_account_that_lost_it_keeps_everything_it_was_handed(monkeypatch, db, tenant, wired):
    """What entered is the account's for good, and a receipt changing hands upstream never reaches back for one."""
    product = await make_product(db, tenant)
    await save(db, UserProduct(user_id=wired["user"].id, product_id=product.id, granted_at=now()))

    await handed_over(monkeypatch, db, tenant, wired)

    assert await db.scalar(select(func.count()).select_from(UserProduct).where(UserProduct.user_id == wired["user"].id)) == 1


async def test_both_accounts_are_written_down_when_a_receipt_moves(monkeypatch, db, tenant, wired):
    heir, subscription, first_owner = await handed_over(monkeypatch, db, tenant, wired)

    entry = (await db.execute(select(SystemLog).where(SystemLog.category == LogCategory.PURCHASE).order_by(SystemLog.id.desc()))).scalars().first()

    assert entry.meta == {"subscription_id": subscription.id, "from_user_id": first_owner, "to_user_id": heir.id}


async def test_the_new_owner_is_delivered_a_cycle_of_their_own(monkeypatch, db, tenant, wired):
    """Whoever holds it now is a different person who just paid, and that is not the cycle the last one had."""
    await promising(db, tenant, wired)

    _, subscription, _ = await handed_over(monkeypatch, db, tenant, wired)

    cycles = (await db.execute(select(SubscriptionBenefit.cycle).where(SubscriptionBenefit.subscription_id == subscription.id))).scalars().all()

    assert cycles and all(cycle == 1 for cycle in cycles)


async def test_reading_the_same_receipt_again_in_the_same_account_moves_nothing(monkeypatch, db, tenant, wired):
    await mirror(monkeypatch, db, wired, answering({"mensal": recurring()}))
    await mirror(monkeypatch, db, wired, answering({"mensal": recurring()}))

    moves = (await db.execute(select(SystemLog).where(SystemLog.description.like("%passed this receipt%")))).scalars().all()

    assert moves == []
    assert (await only_subscription(db)).user_id == wired["user"].id


async def test_a_receipt_that_moved_carries_the_state_the_provider_reports(monkeypatch, db, tenant, wired):
    _, subscription, _ = await handed_over(monkeypatch, db, tenant, wired)

    assert subscription.status == SubscriptionStatus.ACTIVE
    assert subscription.access_until is not None


async def test_a_subscription_starts_when_the_provider_says_it_first_did(monkeypatch, db, wired):
    """The period that is open now is not when the person subscribed, and a reader who came before the integration would read as new."""
    first = now() - timedelta(days=400)

    await mirror(monkeypatch, db, wired, answering({"mensal": recurring(original_purchase_date=first.isoformat().replace("+00:00", "Z"))}))

    subscription = await only_subscription(db)

    assert subscription.started_at.date() == first.date()
    assert subscription.current_period_started_at.date() == (now() - timedelta(days=1)).date()


def test_a_gateway_that_says_nothing_about_how_it_answers_is_refused_where_it_is_declared():
    """A capability that is only checked mid-pass fails over somebody's subscription instead of at import."""
    from services.gateway import PaymentProvider

    with pytest.raises(TypeError, match="says nothing"):

        class Mute(PaymentProvider):
            def authenticate(self, integration, call, secret):
                return None

            pass


def test_a_gateway_that_claims_it_can_be_queried_has_to_implement_it():
    from services.gateway import Credential, PaymentProvider, ProviderEvent

    with pytest.raises(TypeError, match="state_from_query"):

        class Lying(PaymentProvider):
            def authenticate(self, integration, call, secret):
                return None

            queryable = True
            credentials = (Credential("revenuecat_api_key", "Secret key", "the double borrows a column"),)

            async def read(self, integration, call, client):
                return ProviderEvent(external_event_id="x", event_type="y")


def test_a_gateway_that_does_not_say_what_a_call_was_about_is_refused():
    from services.gateway import Credential, PaymentProvider

    with pytest.raises(TypeError, match="does not implement read"):

        class Deaf(PaymentProvider):
            def authenticate(self, integration, call, secret):
                return None

            event_stated = True
            credentials = (Credential("revenuecat_api_key", "Secret key", "the double borrows a column"),)


async def test_a_purchase_the_provider_named_without_a_transaction_is_not_opened(monkeypatch, db, wired):
    """The transaction is what identifies a purchase, so one that arrives without it has nothing to be looked up or opened by."""
    changes = await mirror(monkeypatch, db, wired, answering({"mensal": recurring(store_transaction_id="")}))

    assert changes == 0
    assert await only_subscription(db) is None
    assert any("nothing maps it" in warning for warning in await warnings_of(db))


def test_a_gateway_that_does_not_say_what_to_paste_is_refused():
    from services.gateway import PaymentProvider, ProviderEvent

    with pytest.raises(TypeError, match="has to paste"):

        class Silent(PaymentProvider):
            def authenticate(self, integration, call, secret):
                return None

            event_stated = True

            async def read(self, integration, call, client):
                return ProviderEvent(external_event_id="x", event_type="y")


def test_a_gateway_asking_for_a_place_the_integration_does_not_have_is_refused():
    from services.gateway import Credential, PaymentProvider, ProviderEvent

    with pytest.raises(TypeError, match="nowhere to keep"):

        class Greedy(PaymentProvider):
            def authenticate(self, integration, call, secret):
                return None

            event_stated = True
            credentials = (Credential("merchant_id", "Merchant id", "a place no integration keeps"),)

            async def read(self, integration, call, client):
                return ProviderEvent(external_event_id="x", event_type="y")


async def test_a_key_the_gateway_refuses_is_asked_about_once_and_not_once_per_account(monkeypatch, db, tenant, wired):
    """The sweep answers for a whole base, and a rejected key would otherwise be one call and one error row for every account of it."""
    calls = []

    async def refused(self, request):
        calls.append(1)

        return httpx.Response(401, json={"message": "invalid api key"})

    for index in range(3):
        reader = await user_service.create(db, {"email": f"leitor{index}@acme.com", "password": "s3cret-password", "role": UserRole.NORMAL, "status": UserStatus.ACTIVE, "tenant_id": tenant.id})
        subscription = await make_subscription(db, tenant, reader, wired["plan"], integration_id=wired["integration"].id, external_id=f"txn-{index}")
        subscription.access_until = now() - timedelta(minutes=1)

    await db.commit()

    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", refused)

    assert await reconciliation_service.reconcile_stale(db) == 0
    assert len(calls) == 1, "the second account of a refused key is not asked about"
    assert len(await warnings_of(db)) == 1


async def test_two_base_plans_of_one_google_subscription_are_two_products(monkeypatch, db, tenant, wired):
    """Google sells base plans under one product id, so monthly and annual only tell apart by the plan the query names."""
    anual = await make_plan(db, tenant, code="anual")

    await save(db, ExternalProduct(integration_id=wired["integration"].id, plan_id=wired["plan"].id, external_id="premium:premium-mensal", active=True, meta={}))
    await save(db, ExternalProduct(integration_id=wired["integration"].id, plan_id=anual.id, external_id="premium:premium-anual", active=True, meta={}))

    await mirror(monkeypatch, db, wired, answering({"premium": recurring(product_plan_identifier="premium-anual", store_transaction_id="txn-anual")}))

    subscription = await only_subscription(db)

    assert subscription.plan_id == anual.id, "the base plan is what decides which product was bought"


@pytest.mark.parametrize("header,expected", [("30", 30.0), ("0.5", 1.0), ("999999", 60.0), (None, 1.0), ("soon", 1.0)])
def test_the_pause_a_gateway_asks_for_is_read_in_seconds(header, expected):
    """RevenueCat documents `Retry-After` in seconds, and reading it as milliseconds answers a pause of nothing."""
    assert PROVIDERS[Provider.REVENUECAT].backoff(header) == expected


def test_the_sweep_leaves_the_rest_of_the_pass_time_to_run():
    """The sweep is the first of six steps, and one sized to the whole interval spends the timeout of the task before the other five start."""
    # The pauses are the gaps between the calls, and what the window has left over is what the calls themselves get to spend.
    assert (SWEEP_LIMIT - 1) * PACE < SWEEP_WINDOW.total_seconds()
    assert SWEEP_WINDOW < timedelta(seconds=tasks.tasks["run_subscription_cycle"].timeout)


async def test_the_sweep_paces_between_calls_and_never_after_the_last(monkeypatch, db, tenant, wired):
    """A pause with no call after it buys nothing and is what pushed a full pass past the window it was sized for."""
    product = await db.scalar(select(ExternalProduct))
    second = await save(db, User(tenant_id=tenant.id, email="second@acme.com", password_hash="x", meta={}))

    for user, external in ((wired["user"], "txn-a"), (second, "txn-b")):
        await save(db, Subscription(tenant_id=tenant.id, user_id=user.id, plan_id=wired["plan"].id, integration_id=wired["integration"].id, external_product_id=product.id, external_id=external, status=SubscriptionStatus.ACTIVE, access_until=now() - timedelta(days=1), meta={}))

    pauses = []

    async def counting(seconds):
        pauses.append(seconds)

    monkeypatch.setattr(reconciliation, "asyncio", type("clock", (), {"sleep": staticmethod(counting)}))
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", answering())

    await reconciliation_service.reconcile_stale(db)

    assert pauses == [PACE]


async def test_a_gateway_answering_slowly_never_spends_the_whole_pass(monkeypatch, db, tenant, wired):
    """How long a gateway takes is its business, so the count of accounts bounds nothing and the sweep carries a deadline of its own."""
    product = await db.scalar(select(ExternalProduct))
    second = await save(db, User(tenant_id=tenant.id, email="slow@acme.com", password_hash="x", meta={}))

    for user, external in ((wired["user"], "txn-a"), (second, "txn-b")):
        await save(db, Subscription(tenant_id=tenant.id, user_id=user.id, plan_id=wired["plan"].id, integration_id=wired["integration"].id, external_product_id=product.id, external_id=external, status=SubscriptionStatus.ACTIVE, access_until=now() - timedelta(days=1), meta={}))

    reads = []

    async def slowly(self, request):
        reads.append(request.url)

        monkeypatch.setattr(reconciliation, "now", lambda: now() + SWEEP_WINDOW)

        return httpx.Response(200, json={"subscriber": {"subscriptions": {}, "non_subscriptions": {}}})

    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", slowly)

    await reconciliation_service.reconcile_stale(db)

    assert len(reads) == 1


async def test_a_renewal_that_reports_another_transaction_moves_the_row_onto_it(monkeypatch, db, wired):
    """The store names each period by a transaction of its own, and the row has to answer to the one being sold now."""
    await mirror(monkeypatch, db, wired, answering({"mensal": recurring()}))
    await mirror(monkeypatch, db, wired, answering({"mensal": recurring(store_transaction_id="txn-2")}))

    assert (await only_subscription(db)).external_id == "txn-2"


async def test_an_upgrade_after_a_renewal_is_still_one_purchase(monkeypatch, db, tenant, wired):
    """A row left carrying the transaction before is a row the upgrade cannot find, and a second one opened for it pays the cycle again."""
    annual = await make_plan(db, tenant, code="anual", name="Anual")
    await save(db, ExternalProduct(integration_id=wired["integration"].id, plan_id=annual.id, external_id="anual", active=True, meta={}))

    await mirror(monkeypatch, db, wired, answering({"mensal": recurring()}))
    await mirror(monkeypatch, db, wired, answering({"mensal": recurring(store_transaction_id="txn-2")}))
    await mirror(monkeypatch, db, wired, answering({"anual": recurring(store_transaction_id="txn-2")}))

    rows = (await db.execute(select(Subscription))).scalars().all()

    assert len(rows) == 1
    assert rows[0].plan_id == annual.id
    assert rows[0].status == SubscriptionStatus.ACTIVE


async def test_a_transaction_another_row_already_carries_is_never_taken_from_it(monkeypatch, db, tenant, wired):
    """A receipt reaching an account that had already bought that product is answered by the row it has, because one transaction is one row of an integration and taking it is the unique index answering a five hundred."""
    product = await db.scalar(select(ExternalProduct))
    stranger = await save(db, User(tenant_id=tenant.id, email="outra@acme.com", password_hash="x", meta={}))

    theirs = await save(db, Subscription(tenant_id=tenant.id, user_id=stranger.id, plan_id=wired["plan"].id, integration_id=wired["integration"].id, external_product_id=product.id, external_id="txn-1", status=SubscriptionStatus.ACTIVE, meta={}))
    mine = await save(db, Subscription(tenant_id=tenant.id, user_id=wired["user"].id, plan_id=wired["plan"].id, integration_id=wired["integration"].id, external_product_id=product.id, external_id="txn-antiga", status=SubscriptionStatus.EXPIRED, meta={}))

    await mirror(monkeypatch, db, wired, answering({"mensal": recurring()}))
    await db.refresh(mine)
    await db.refresh(theirs)

    # The product is what finds the row, so nothing is opened and nothing changes hands.
    assert len((await db.execute(select(Subscription))).scalars().all()) == 2
    assert mine.external_id == "txn-antiga"
    assert mine.status == SubscriptionStatus.ACTIVE
    assert theirs.user_id == stranger.id
