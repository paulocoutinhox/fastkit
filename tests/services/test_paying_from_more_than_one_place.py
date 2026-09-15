"""One account paying the app store, play and a partner at the same time, which is a state nobody here gets to refuse."""

from datetime import timedelta

import httpx
import pytest
from sqlalchemy import select

from enums.integration import Provider
from enums.subscription import BenefitCadence, BenefitType, SubscriptionStatus
from helpers.dates import now
from helpers.security import encrypt
from models.integration import ExternalProduct
from models.subscription import Subscription, SubscriptionBenefit
from services.delivery import delivery_service
from services.reconciliation import reconciliation_service
from tests.factories import make_benefit, make_entitlement, make_integration, make_plan, make_plan_entitlement, make_subscription, save

APPLE = "acme.premium.monthly"
GOOGLE = "premium:premium-monthly"


def sold(store: str, transaction: str) -> dict:
    return {"expires_date": (now() + timedelta(days=30)).isoformat().replace("+00:00", "Z"), "period_type": "NORMAL", "store": store, "ownership_type": "PURCHASED", "is_sandbox": False, "store_transaction_id": transaction, "purchase_date": (now() - timedelta(days=1)).isoformat().replace("+00:00", "Z")}


@pytest.fixture
async def wired(currency, db, tenant, member):
    """One project of the gateway covers the two stores, so the same plan is sold under two product references."""
    integration = await make_integration(db, tenant, provider=Provider.REVENUECAT, revenuecat_api_key_encrypted=encrypt("sk-revenuecat"))
    plan = await make_plan(db, tenant)
    entitlement = await make_entitlement(db, tenant)

    await make_plan_entitlement(db, plan, entitlement)
    await make_benefit(db, entitlement, type=BenefitType.CREDIT, target="coins", currency_id=currency.id, quantity=10, cadence=BenefitCadence.ON_ACTIVATION)

    for reference in (APPLE, GOOGLE):
        await save(db, ExternalProduct(integration_id=integration.id, plan_id=plan.id, external_id=reference, active=True, meta={}))

    return {"integration": integration, "member": member, "plan": plan, "tenant": tenant}


async def read_by(monkeypatch, db, wired, subscriptions: dict) -> None:
    async def responder(self, request):
        return httpx.Response(200, json={"subscriber": {"subscriptions": subscriptions, "non_subscriptions": {}}})

    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", responder)
    await reconciliation_service.reconcile_account(db, wired["integration"], wired["member"])


async def rows(db) -> list[Subscription]:
    return list((await db.execute(select(Subscription).order_by(Subscription.id))).scalars())


async def partner(db, wired, **overrides) -> Subscription:
    """A gateway that is not a store, and whose answer this side never gets to argue with."""
    integration = await make_integration(db, wired["tenant"], provider=Provider.STRIPE)
    product = await save(db, ExternalProduct(integration_id=integration.id, plan_id=wired["plan"].id, external_id="carrier-premium", active=True, meta={}))
    subscription = await make_subscription(db, wired["tenant"], wired["member"], wired["plan"], integration_id=integration.id, external_product_id=product.id, external_id="carrier-1", access_until=now() + timedelta(days=30), **overrides)

    await delivery_service.activate(db, subscription)

    return subscription


async def balance_of(db, user, currency) -> int:
    """What the account holds of one currency, read from the balance the ledger of that currency explains."""
    from services.account import user_balance_service

    held = await user_balance_service.list_for_user(db, user.id)

    return next((row.amount for row in held if row.currency_id == currency.id), 0)


async def test_paying_on_both_stores_opens_one_subscription_for_each(monkeypatch, db, wired):
    await read_by(monkeypatch, db, wired, {APPLE: sold("APP_STORE", "apple-1"), GOOGLE: sold("PLAY_STORE", "google-1")})

    held = await rows(db)

    assert [row.status for row in held] == [SubscriptionStatus.ACTIVE, SubscriptionStatus.ACTIVE]
    assert sorted(row.external_id for row in held) == ["apple-1", "google-1"]


async def test_one_store_ending_leaves_the_other_paying(monkeypatch, db, wired):
    """Whoever cancels on the iphone keeps what the android is still paying for."""
    await read_by(monkeypatch, db, wired, {APPLE: sold("APP_STORE", "apple-1"), GOOGLE: sold("PLAY_STORE", "google-1")})
    await read_by(monkeypatch, db, wired, {GOOGLE: sold("PLAY_STORE", "google-1")})

    held = {row.external_id: row.status for row in await rows(db)}

    assert held == {"apple-1": SubscriptionStatus.EXPIRED, "google-1": SubscriptionStatus.ACTIVE}


async def test_a_gateway_never_closes_what_another_gateway_sold(monkeypatch, db, wired):
    """The partner says the account is subscribed, and the store answering for nothing cannot take that away."""
    outside = await partner(db, wired)

    await read_by(monkeypatch, db, wired, {})

    held = {row.external_id: row.status for row in await rows(db)}

    assert held[outside.external_id] == SubscriptionStatus.ACTIVE, "a reconciliation is scoped to its own integration, and a leftover is only a leftover inside it"
    assert held == {"carrier-1": SubscriptionStatus.ACTIVE}


async def test_three_places_paying_at_once_is_three_subscriptions(monkeypatch, db, wired):
    await partner(db, wired)
    await read_by(monkeypatch, db, wired, {APPLE: sold("APP_STORE", "apple-1"), GOOGLE: sold("PLAY_STORE", "google-1")})

    held = await rows(db)

    assert sorted(row.external_id for row in held) == ["apple-1", "carrier-1", "google-1"]
    assert {row.status for row in held} == {SubscriptionStatus.ACTIVE}


async def test_what_the_account_is_owed_is_the_sum_of_what_it_pays_for(monkeypatch, db, member, wired, currency):
    """Each subscription promises on its own, because each one was paid for on its own."""
    await partner(db, wired)
    await read_by(monkeypatch, db, wired, {APPLE: sold("APP_STORE", "apple-1"), GOOGLE: sold("PLAY_STORE", "google-1")})
    await db.refresh(member)

    assert await balance_of(db, member, currency) == 30


async def test_a_new_cycle_moves_only_the_benefits_of_the_subscription_that_opened_it(db, tenant, member, wired, monkeypatch):
    """The account pays two places, and one starting over never moves the cycle of the other."""
    outside = await partner(db, wired)

    await read_by(monkeypatch, db, wired, {APPLE: sold("APP_STORE", "apple-1")})

    released = await delivery_service.release_cycle(db, outside)
    cycles = {row.subscription_id: row.cycle for row in (await db.execute(select(SubscriptionBenefit))).scalars()}

    assert released == 1
    assert cycles[outside.id] == 1
    assert [cycle for subscription_id, cycle in cycles.items() if subscription_id != outside.id] == [0]
