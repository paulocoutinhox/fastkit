import json
from datetime import timedelta

import pytest
from sqlalchemy import select

from enums.subscription import BenefitCadence, BenefitGrantStatus, BenefitType, IntervalUnit, SubscriptionStatus
from helpers.dates import now
from jobs.subscription import run_subscription_cycle
from models.subscription import BenefitGrant, SubscriptionBenefit
from services.delivery import delivery_service
from tests.factories import make_benefit, make_entitlement, make_plan, make_plan_entitlement, make_subscription


async def build_subscription(db, tenant, member, **benefit_overrides):
    plan = await make_plan(db, tenant)
    entitlement = await make_entitlement(db, tenant)

    await make_plan_entitlement(db, plan, entitlement)
    await make_benefit(db, entitlement, **benefit_overrides)

    return await make_subscription(db, tenant, member, plan)


async def balance_of(db, user, currency) -> int:
    """What the account holds of one currency, read from the balance the ledger of that currency explains."""
    from services.account import user_balance_service

    held = await user_balance_service.list_for_user(db, user.id)

    return next((row.amount for row in held if row.currency_id == currency.id), 0)


async def test_process_due_benefits_runs_the_cycles(db, tenant, member, currency):
    subscription = await build_subscription(db, tenant, member, type=BenefitType.CREDIT, currency_id=currency.id, target="gold", quantity=10, cadence=BenefitCadence.RECURRING, interval_unit=IntervalUnit.MONTH, interval_value=1, grant_on_activation=False)

    await delivery_service.activate(db, subscription)

    snapshot = (await db.execute(select(SubscriptionBenefit))).scalars().one()
    snapshot.next_grant_at = now() - timedelta(minutes=1)
    await db.commit()

    await run_subscription_cycle(db)
    await db.refresh(member)

    assert await balance_of(db, member, currency) == 10


async def test_expire_subscriptions_closes_what_is_over(db, tenant, member):
    subscription = await build_subscription(db, tenant, member)

    subscription.access_until = now() - timedelta(days=1)
    await db.commit()

    await run_subscription_cycle(db)
    await db.refresh(subscription)

    assert subscription.status == SubscriptionStatus.EXPIRED


async def test_retry_failed_grants_picks_the_failures_up(db, tenant, member, monkeypatch, currency):
    async def broken(currency, *args, **kwargs):
        raise RuntimeError("provider down")

    subscription = await build_subscription(db, tenant, member, type=BenefitType.CREDIT, currency_id=currency.id, target="gold", quantity=10)

    monkeypatch.setattr(delivery_service, "deliver_credit", broken)
    await delivery_service.activate(db, subscription)
    monkeypatch.undo()

    await run_subscription_cycle(db)

    grant = (await db.execute(select(BenefitGrant))).scalars().one()
    await db.refresh(grant)

    assert grant.status == BenefitGrantStatus.COMPLETED


async def test_retry_failed_webhooks_picks_up_what_the_gateway_stopped_resending(db, tenant, member, monkeypatch):
    """RevenueCat gives up after five tries, so an event stuck as failed only moves if this side goes back to it."""
    import httpx

    from enums.integration import Provider, WebhookEventStatus
    from helpers.security import encrypt
    from models.integration import ExternalProduct, WebhookEvent
    from services import webhook as module
    from tests.factories import make_integration
    from tests.routes.test_webhook import event as revenuecat_event

    integration = await make_integration(db, tenant, provider=Provider.REVENUECAT, revenuecat_api_key_encrypted=encrypt("sk"))
    plan = await make_plan(db, tenant)

    db.add(ExternalProduct(integration_id=integration.id, plan_id=plan.id, external_id="premium_monthly", active=True, meta={}))
    await db.commit()

    async def broken(*args, **kwargs):
        raise RuntimeError("provider down")

    call = module.InboundCall(method="POST", headers={"content-type": "application/json"}, body=json.dumps(revenuecat_event("INITIAL_PURCHASE", member)).encode())

    monkeypatch.setattr(module.PROVIDERS[Provider.REVENUECAT], "state_from_query", broken)

    with pytest.raises(RuntimeError):
        await module.webhook_service.ingest(db, integration, call)

    monkeypatch.undo()

    async def answering(self, request):
        return httpx.Response(
            200, json={"subscriber": {"subscriptions": {"premium_monthly": {"expires_date": (now() + timedelta(days=30)).isoformat().replace("+00:00", "Z"), "period_type": "NORMAL", "store": "APP_STORE", "is_sandbox": False, "store_transaction_id": "txn-1", "purchase_date": now().isoformat().replace("+00:00", "Z")}}}}
        )

    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", answering)
    await run_subscription_cycle(db)

    record = (await db.execute(select(WebhookEvent))).scalars().one()
    await db.refresh(record)

    assert record.status == WebhookEventStatus.COMPLETED


async def test_a_failed_event_the_provider_cannot_read_stops_being_retried(db, tenant):
    """The body is not the shape that gateway sends, so retrying it forever would be a queue that never drains."""
    from enums.integration import Provider, WebhookEventStatus
    from models.integration import WebhookEvent
    from tests.factories import make_integration

    integration = await make_integration(db, tenant, provider=Provider.STRIPE)

    db.add(WebhookEvent(tenant_id=tenant.id, integration_id=integration.id, external_event_id="x", payload_hash="x", error_code="unread", status=WebhookEventStatus.FAILED, payload={"nothing": 1}, meta={}))
    await db.commit()

    await run_subscription_cycle(db)

    record = (await db.execute(select(WebhookEvent))).scalars().one()
    await db.refresh(record)

    assert record.status == WebhookEventStatus.IGNORED


async def test_the_cycle_runs_every_step_in_one_order(db, monkeypatch):
    """The provider speaks before the clock closes anything, and one pass is what keeps the two from racing."""
    from services import reconciliation as reconciliation_module
    from services import webhook as webhook_module

    order = []

    async def note(name, answer):
        order.append(name)

        return answer

    monkeypatch.setattr(reconciliation_module.reconciliation_service, "reconcile_stale", lambda s, **k: note("reconcile", 0))
    monkeypatch.setattr(delivery_service, "expire_subscriptions", lambda s, **k: note("expire", []))
    monkeypatch.setattr(delivery_service, "process_due", lambda s, **k: note("deliver", []))
    monkeypatch.setattr(delivery_service, "retry_failed_grants", lambda s, **k: note("retry_grants", []))
    monkeypatch.setattr(webhook_module.webhook_service, "retry_failed", lambda s, **k: note("retry_events", []))

    answer = await run_subscription_cycle(db)

    assert order == ["reconcile", "expire", "deliver", "retry_grants", "retry_events"]
    assert set(answer) == {"reconciled", "expired", "delivered", "retried_grants", "retried_events"}


async def test_the_cron_opens_its_own_session_and_runs_the_cycle(monkeypatch):
    """The scheduler calls this one, and it is the only difference between the job and the cycle it runs."""
    from jobs import subscription as job

    ran = []

    async def counting(session):
        ran.append(session)

        return {"reconciled": 0}

    monkeypatch.setattr(job, "run_subscription_cycle", counting)
    await job.subscription_cycle()

    assert len(ran) == 1
