from datetime import timedelta

from sqlalchemy import select

from enums.benefit_cadence import BenefitCadence
from enums.benefit_grant_status import BenefitGrantStatus
from enums.benefit_policy import BenefitPolicy
from enums.benefit_status import BenefitStatus
from enums.benefit_type import BenefitType
from enums.interval_unit import IntervalUnit
from enums.log_level import LogLevel
from enums.subscription_status import SubscriptionStatus
from enums.user_entitlement_status import UserEntitlementStatus
from helpers.dates import now
from helpers.db import AsyncSessionLocal
from models.benefit_grant import BenefitGrant
from models.plan import Plan
from models.subscription import Subscription
from models.subscription_benefit import SubscriptionBenefit
from models.system_log import SystemLog
from models.user_entitlement import UserEntitlement
from models.user_product import UserProduct
from services.delivery_service import ABANDONED_AFTER, MAX_ATTEMPTS, delivery_service
from tests.factories import make_benefit, make_entitlement, make_plan, make_plan_entitlement, make_product, make_subscription


async def build(currency, db, tenant, member):
    plan = await make_plan(db, tenant)
    entitlement = await make_entitlement(db, tenant)

    await make_plan_entitlement(db, plan, entitlement)
    await make_benefit(db, entitlement, type=BenefitType.CREDIT, currency_id=currency.id, target="gold", quantity=50)

    return await make_subscription(db, tenant, member, plan)


async def abandon(db, grant, age):
    """What a container killed between the two commits of a cycle leaves behind."""
    grant.status = BenefitGrantStatus.PROCESSING
    grant.completed_at = None
    grant.started_at = now() - age
    await db.commit()


async def balance_of(db, user, currency) -> int:
    """What the account holds of one currency, read from the balance the ledger of that currency explains."""
    from services.user_balance_service import user_balance_service

    await db.refresh(user)
    held = await user_balance_service.list_for_user(db, user.id)

    return next((row.amount for row in held if row.currency_id == currency.id), 0)


async def test_a_node_that_died_mid_delivery_leaves_the_grant_recoverable(db, tenant, member, currency):
    """The key that stops a double delivery would otherwise stop the delivery happening at all."""
    subscription = await build(currency, db, tenant, member)
    grant = (await delivery_service.activate(db, subscription))[0]

    await abandon(db, grant, ABANDONED_AFTER + timedelta(minutes=1))

    retried = await delivery_service.retry_failed_grants(db)

    assert [row.id for row in retried] == [grant.id]
    assert grant.status == BenefitGrantStatus.COMPLETED


async def test_a_grant_whose_last_attempt_died_is_given_up_on_instead_of_held_forever(db, tenant, member, currency):
    """No pass may take it again, and a benefit whose grant stays processing is met by every pass and never delivers another cycle."""
    subscription = await build(currency, db, tenant, member)
    grant = (await delivery_service.activate(db, subscription))[0]

    await abandon(db, grant, ABANDONED_AFTER + timedelta(minutes=1))
    grant.attempts = MAX_ATTEMPTS
    await db.commit()

    held = await balance_of(db, member, currency)
    retried = await delivery_service.retry_failed_grants(db)

    assert [row.id for row in retried] == [grant.id]
    assert (grant.status, grant.error_code) == (BenefitGrantStatus.SKIPPED, "given_up_after_max_attempts")
    assert await balance_of(db, member, currency) == held
    assert await delivery_service.retry_failed_grants(db) == []


async def test_a_grant_another_pass_already_closed_is_not_closed_twice(db, tenant, member, currency):
    """The close is taken the way a claim is, so the pass that lost reads that it did and touches nothing."""
    subscription = await build(currency, db, tenant, member)
    grant = (await delivery_service.activate(db, subscription))[0]

    assert await delivery_service.close_exhausted(db, grant.id) is False


async def test_a_grant_a_live_node_is_still_working_on_is_left_alone(db, tenant, member, currency):
    """Another instance may be delivering it right now, and stealing it is how one cycle pays twice."""
    subscription = await build(currency, db, tenant, member)
    grant = (await delivery_service.activate(db, subscription))[0]

    await abandon(db, grant, timedelta(minutes=1))

    assert await delivery_service.retry_failed_grants(db) == []
    assert grant.status == BenefitGrantStatus.PROCESSING


async def test_recovering_a_cycle_never_pays_the_wallet_twice(db, tenant, member, currency):
    subscription = await build(currency, db, tenant, member)
    grant = (await delivery_service.activate(db, subscription))[0]

    await db.refresh(member)
    before = await balance_of(db, member, currency)

    await abandon(db, grant, ABANDONED_AFTER + timedelta(minutes=1))
    await delivery_service.retry_failed_grants(db)
    await db.refresh(member)

    assert before == 50
    assert await balance_of(db, member, currency) == 50


async def test_recovering_a_cycle_never_hands_the_same_product_over_twice(db, tenant, member):
    """What the account already owns is not handed over again, so a second run finds nothing left to give."""
    plan = await make_plan(db, tenant)
    entitlement = await make_entitlement(db, tenant)
    product = await make_product(db, tenant)

    await make_plan_entitlement(db, plan, entitlement)
    await make_benefit(db, entitlement, type=BenefitType.PRODUCT, target="handbook", quantity=1, product_id=product.id)

    subscription = await make_subscription(db, tenant, member, plan)
    grant = (await delivery_service.activate(db, subscription))[0]

    await abandon(db, grant, ABANDONED_AFTER + timedelta(minutes=1))
    await delivery_service.retry_failed_grants(db)

    owned = (await db.execute(select(UserProduct))).scalars().all()

    assert [row.product_id for row in owned] == [product.id]


async def test_a_grant_left_behind_by_a_subscription_that_ended_never_reopens_its_access(db, tenant, member):
    """What the subscription owed when the cycle ran it stopped owing when it expired, and a retry that delivered it would hand the catalog back."""
    plan = await make_plan(db, tenant)
    entitlement = await make_entitlement(db, tenant)

    await make_plan_entitlement(db, plan, entitlement)
    await make_benefit(db, entitlement, type=BenefitType.ACCESS, target="premium")

    subscription = await make_subscription(db, tenant, member, plan, access_until=now() + timedelta(days=1))
    grant = (await delivery_service.activate(db, subscription))[0]

    await abandon(db, grant, ABANDONED_AFTER + timedelta(minutes=1))

    subscription.access_until = now() - timedelta(days=1)
    await db.commit()
    await delivery_service.expire_subscriptions(db)

    await delivery_service.retry_failed_grants(db)

    rows = (await db.execute(select(UserEntitlement).where(UserEntitlement.subscription_id == subscription.id))).scalars().all()

    assert grant.status == BenefitGrantStatus.SKIPPED
    assert grant.error_code == "subscription_no_longer_eligible"
    assert [row.status for row in rows] == [UserEntitlementStatus.EXPIRED]


async def test_a_grant_of_a_subscription_the_store_paused_is_closed_instead_of_handed_over(db, tenant, member, currency):
    """A pause suspends what the subscription hands over, and the benefit stays on it while the schedule waits."""
    subscription = await build(currency, db, tenant, member)
    grant = (await delivery_service.activate(db, subscription))[0]

    await abandon(db, grant, ABANDONED_AFTER + timedelta(minutes=1))
    await db.refresh(member)
    before = await balance_of(db, member, currency)

    subscription.status = SubscriptionStatus.SUSPENDED
    subscription.benefit_status = BenefitStatus.PAUSED
    await db.commit()

    await delivery_service.retry_failed_grants(db)
    await db.refresh(member)

    assert grant.status == BenefitGrantStatus.SKIPPED
    assert grant.error_code == "subscription_no_longer_eligible"
    assert await balance_of(db, member, currency) == before


async def test_recovering_an_access_benefit_leaves_the_entitlement_active(db, tenant, member):
    plan = await make_plan(db, tenant)
    entitlement = await make_entitlement(db, tenant)

    await make_plan_entitlement(db, plan, entitlement)
    await make_benefit(db, entitlement, type=BenefitType.ACCESS, target="premium")

    subscription = await make_subscription(db, tenant, member, plan)
    grant = (await delivery_service.activate(db, subscription))[0]

    await abandon(db, grant, ABANDONED_AFTER + timedelta(minutes=1))
    await delivery_service.retry_failed_grants(db)

    rows = (await db.execute(select(UserEntitlement).where(UserEntitlement.subscription_id == subscription.id))).scalars().all()

    assert [row.status for row in rows] == [UserEntitlementStatus.ACTIVE]


async def test_cancellation_after_claim_cannot_reopen_access(db, tenant, member, monkeypatch):
    plan = await make_plan(db, tenant)
    entitlement = await make_entitlement(db, tenant)

    await make_plan_entitlement(db, plan, entitlement)
    await make_benefit(db, entitlement, type=BenefitType.ACCESS, target="premium")

    subscription = await make_subscription(db, tenant, member, plan)
    grant = (await delivery_service.activate(db, subscription))[0]
    subscription_id = subscription.id
    grant_id = grant.id

    await abandon(db, grant, ABANDONED_AFTER + timedelta(minutes=1))
    claim = delivery_service.claim

    async def claim_then_cancel(session, identity):
        claimed = await claim(session, identity)

        async with AsyncSessionLocal() as other:
            ended = await other.get(Subscription, subscription_id)
            ended.status = SubscriptionStatus.EXPIRED
            ended.benefit_status = BenefitStatus.ENDED
            await delivery_service.end_benefits(other, ended)
            await other.commit()

        return claimed

    monkeypatch.setattr(delivery_service, "claim", claim_then_cancel)

    async with AsyncSessionLocal() as retry:
        await delivery_service.retry_failed_grants(retry)

    async with AsyncSessionLocal() as reader:
        closed = await reader.get(BenefitGrant, grant_id)
        statuses = (await reader.scalars(select(UserEntitlement.status).where(UserEntitlement.subscription_id == subscription_id))).all()

    assert statuses == [UserEntitlementStatus.EXPIRED]
    assert closed.status == BenefitGrantStatus.SKIPPED
    assert closed.error_code == "subscription_no_longer_eligible"


async def test_a_replaced_cycle_cannot_deliver_its_abandoned_grant(db, tenant, member, currency, monkeypatch):
    subscription = await build(currency, db, tenant, member)

    async def fail(session, benefit, grant):
        raise RuntimeError("Delivery interrupted before the wallet move.")

    with monkeypatch.context() as failing:
        failing.setattr(delivery_service, "deliver_credit", fail)
        grant = (await delivery_service.activate(db, subscription))[0]

    assert await balance_of(db, member, currency) == 0

    await delivery_service.release_cycle(db, subscription)
    await delivery_service.retry_failed_grants(db)

    assert await balance_of(db, member, currency) == 0
    assert grant.status == BenefitGrantStatus.SKIPPED
    assert grant.error_code == "cycle_replaced"


async def test_a_grant_that_ran_out_of_attempts_closes_the_cycle_and_says_why(db, tenant, member, monkeypatch, currency):
    """A failure nobody will pick up again would hold the schedule forever and end the benefit in silence."""
    subscription = await build(currency, db, tenant, member)

    async def unreachable(session, benefit, grant):
        raise RuntimeError("the wallet is unreachable")

    monkeypatch.setattr(delivery_service, "deliver_credit", unreachable)

    grant = (await delivery_service.activate(db, subscription))[0]

    for _ in range(MAX_ATTEMPTS):
        await delivery_service.retry_failed_grants(db)

    reported = (await db.execute(select(SystemLog).where(SystemLog.level == LogLevel.ERROR))).scalars().all()

    assert grant.attempts == MAX_ATTEMPTS
    assert grant.status == BenefitGrantStatus.SKIPPED
    assert grant.error_code == "given_up_after_max_attempts"
    assert grant.error_message == "the wallet is unreachable", "what failed is kept, because the reason is what somebody acts on"
    assert [row.meta["benefit_grant_id"] for row in reported] == [grant.id]


async def test_a_cycle_waiting_on_the_retry_pass_is_left_to_it_and_takes_no_place_in_the_due_batch(db, tenant, member, currency):
    """A misconfigured benefit on a large plan fails every cycle, and read again on every pass it filled the batch every other benefit waits behind."""
    plan = await make_plan(db, tenant)
    entitlement = await make_entitlement(db, tenant)

    await make_plan_entitlement(db, plan, entitlement)
    await make_benefit(db, entitlement, type=BenefitType.CREDIT, currency_id=currency.id, target="gold", quantity=50, cadence=BenefitCadence.RECURRING, interval_unit=IntervalUnit.MONTH, interval_value=1)

    subscription = await make_subscription(db, tenant, member, plan)
    grant = (await delivery_service.activate(db, subscription))[0]
    benefit = await db.get(SubscriptionBenefit, grant.subscription_benefit_id)

    grant.status = BenefitGrantStatus.FAILED
    benefit.next_grant_at = now() - timedelta(minutes=1)
    await db.commit()

    assert await delivery_service.process_due(db) == []

    grant.status = BenefitGrantStatus.COMPLETED
    await db.commit()

    assert len(await delivery_service.process_due(db)) == 1


async def test_a_rolled_back_delivery_does_not_stop_the_rest_of_an_activation(db, tenant, member, currency, monkeypatch):
    from sqlalchemy.exc import OperationalError

    subscription = await build_batch(currency, db, tenant, member)
    deliver = delivery_service.deliver_credit
    attempted = 0

    async def interrupted(session, benefit, grant):
        nonlocal attempted
        attempted += 1

        if attempted == 2:
            await session.execute(select(1))
            await session.rollback()

            raise OperationalError("INSERT", {}, RuntimeError("database connection interrupted"))

        await deliver(session, benefit, grant)

    monkeypatch.setattr(delivery_service, "deliver_credit", interrupted)

    grants = await delivery_service.activate(db, subscription)

    assert [grant.status for grant in grants] == [BenefitGrantStatus.COMPLETED, BenefitGrantStatus.FAILED, BenefitGrantStatus.COMPLETED]
    assert grants[1].error_code == "OperationalError"


async def build_batch(currency, db, tenant, member, grant_on_activation=True):
    plan = await make_plan(db, tenant)
    entitlement = await make_entitlement(db, tenant)

    await make_plan_entitlement(db, plan, entitlement)

    for target in ("first", "second", "third"):
        await make_benefit(db, entitlement, type=BenefitType.CREDIT, currency_id=currency.id, target=target, quantity=50, cadence=BenefitCadence.RECURRING, interval_unit=IntervalUnit.MONTH, interval_value=1, grant_on_activation=grant_on_activation)

    return await make_subscription(db, tenant, member, plan)


async def test_a_rolled_back_delivery_does_not_stop_the_due_batch(db, tenant, member, currency, monkeypatch):
    from sqlalchemy.exc import OperationalError

    subscription = await build_batch(currency, db, tenant, member, grant_on_activation=False)
    await delivery_service.activate(db, subscription)
    deliver = delivery_service.deliver_credit
    attempted = 0

    async def interrupted(session, benefit, grant):
        nonlocal attempted
        attempted += 1

        if attempted == 2:
            await session.execute(select(1))
            await session.rollback()

            raise OperationalError("INSERT", {}, RuntimeError("database connection interrupted"))

        await deliver(session, benefit, grant)

    monkeypatch.setattr(delivery_service, "deliver_credit", interrupted)

    grants = await delivery_service.process_due(db)

    assert [grant.status for grant in grants] == [BenefitGrantStatus.COMPLETED, BenefitGrantStatus.FAILED, BenefitGrantStatus.COMPLETED]
    assert grants[1].error_code == "OperationalError"


async def test_a_rolled_back_retry_does_not_stop_the_remaining_grants(db, tenant, member, currency, monkeypatch):
    from sqlalchemy.exc import OperationalError

    subscription = await build_batch(currency, db, tenant, member)
    deliver = delivery_service.deliver_credit

    async def failed(session, benefit, grant):
        raise RuntimeError("the wallet is unavailable")

    monkeypatch.setattr(delivery_service, "deliver_credit", failed)
    await delivery_service.activate(db, subscription)
    attempted = 0

    async def interrupted(session, benefit, grant):
        nonlocal attempted
        attempted += 1

        if attempted == 2:
            await session.execute(select(1))
            await session.rollback()

            raise OperationalError("INSERT", {}, RuntimeError("database connection interrupted"))

        await deliver(session, benefit, grant)

    monkeypatch.setattr(delivery_service, "deliver_credit", interrupted)

    grants = await delivery_service.retry_failed_grants(db)

    assert [grant.status for grant in grants] == [BenefitGrantStatus.COMPLETED, BenefitGrantStatus.FAILED, BenefitGrantStatus.COMPLETED]
    assert [grant.attempts for grant in grants] == [2, 2, 2]


async def test_a_product_grant_does_not_keep_ownership_when_its_credits_fail(db, tenant, member, currency, monkeypatch):
    from sqlalchemy import func
    from sqlalchemy.exc import OperationalError

    from services.credit_transaction_service import credit_transaction_service

    plan = await make_plan(db, tenant)
    entitlement = await make_entitlement(db, tenant)
    product = await make_product(db, tenant, credits=10, credits_currency_id=currency.id)

    await make_plan_entitlement(db, plan, entitlement)
    await make_benefit(db, entitlement, type=BenefitType.PRODUCT, target="bundle", product_id=product.id)
    subscription = await make_subscription(db, tenant, member, plan)
    move = credit_transaction_service.move

    async def interrupted(session, *args, **kwargs):
        await session.execute(select(1))

        raise OperationalError("UPDATE", {}, RuntimeError("wallet write interrupted"))

    monkeypatch.setattr(credit_transaction_service, "move", interrupted)

    grants = await delivery_service.activate(db, subscription)

    assert grants[0].status == BenefitGrantStatus.FAILED
    assert await db.scalar(select(func.count()).select_from(UserProduct)) == 0

    monkeypatch.setattr(credit_transaction_service, "move", move)

    retried = await delivery_service.retry_failed_grants(db)

    assert retried[0].status == BenefitGrantStatus.COMPLETED
    assert await db.scalar(select(func.count()).select_from(UserProduct)) == 1
    assert await balance_of(db, member, currency) == 10


async def test_a_completed_old_cycle_cannot_advance_the_replacement_calendar(db, tenant, member, currency, monkeypatch):
    subscription = await build(currency, db, tenant, member)
    subscription_id = subscription.id
    deliver = delivery_service.deliver_credit

    async def deliver_then_replace(session, benefit, grant):
        await deliver(session, benefit, grant)

        async with AsyncSessionLocal() as other:
            current = await other.get(Subscription, subscription_id)
            await delivery_service.release_cycle(other, current)

    monkeypatch.setattr(delivery_service, "deliver_credit", deliver_then_replace)
    grant = (await delivery_service.activate(db, subscription))[0]
    snapshot = await db.get(SubscriptionBenefit, grant.subscription_benefit_id, populate_existing=True)

    assert grant.status == BenefitGrantStatus.COMPLETED
    assert snapshot.cycle == 1
    assert snapshot.last_grant_at is None
    assert await balance_of(db, member, currency) == 50


async def test_a_retry_rechecks_the_plan_policy_after_claim(db, tenant, member, currency, monkeypatch):
    subscription = await build(currency, db, tenant, member)
    subscription_id = subscription.id

    async def fail(session, benefit, grant):
        raise RuntimeError("Delivery interrupted before the wallet move.")

    with monkeypatch.context() as failing:
        failing.setattr(delivery_service, "deliver_credit", fail)
        grant = (await delivery_service.activate(db, subscription))[0]

    assert grant.status == BenefitGrantStatus.FAILED
    claim = delivery_service.claim

    async def claim_then_trial(session, identity):
        claimed = await claim(session, identity)

        async with AsyncSessionLocal() as other:
            current = await other.get(Subscription, subscription_id)
            current.status = SubscriptionStatus.TRIALING
            plan = await other.get(Plan, current.plan_id)
            plan.trial_benefit_policy = BenefitPolicy.ACCESS_ONLY
            await other.commit()

        return claimed

    monkeypatch.setattr(delivery_service, "claim", claim_then_trial)

    async with AsyncSessionLocal() as retry:
        retried = await delivery_service.retry_failed_grants(retry)

    assert retried[0].status == BenefitGrantStatus.SKIPPED
    assert retried[0].error_code == "withheld_by_plan_policy"
    assert await balance_of(db, member, currency) == 0


async def test_activation_rereads_a_subscription_closed_by_another_session(db, tenant, member):
    plan = await make_plan(db, tenant)
    entitlement = await make_entitlement(db, tenant)
    await make_plan_entitlement(db, plan, entitlement)
    await make_benefit(db, entitlement, type=BenefitType.ACCESS, target="premium")
    subscription = await make_subscription(db, tenant, member, plan)
    subscription_id = subscription.id
    await delivery_service.activate(db, subscription)

    async with AsyncSessionLocal() as other:
        ended = await other.get(Subscription, subscription_id)
        ended.status = SubscriptionStatus.EXPIRED
        ended.benefit_status = BenefitStatus.ENDED
        await delivery_service.end_benefits(other, ended)
        await other.commit()

    assert await delivery_service.activate(db, subscription) == []
    statuses = (await db.scalars(select(UserEntitlement.status).where(UserEntitlement.subscription_id == subscription_id))).all()
    assert statuses == [UserEntitlementStatus.EXPIRED]


async def test_activation_refreshes_cached_entitlements_and_benefit_snapshots(db, tenant, member):
    plan = await make_plan(db, tenant)
    entitlement = await make_entitlement(db, tenant)
    await make_plan_entitlement(db, plan, entitlement)
    await make_benefit(db, entitlement, type=BenefitType.ACCESS, target="premium")
    subscription = await make_subscription(db, tenant, member, plan)
    grant = (await delivery_service.activate(db, subscription))[0]
    held = await db.get(UserEntitlement, grant.subscription_benefit.user_entitlement_id)
    snapshot = grant.subscription_benefit
    subscription_id = subscription.id

    async with AsyncSessionLocal() as other:
        current = await other.get(Subscription, subscription_id)
        await delivery_service.end_benefits(other, current)
        await other.commit()

    assert held.status == UserEntitlementStatus.ACTIVE
    assert snapshot.status == BenefitStatus.ACTIVE

    await delivery_service.activate(db, subscription)

    async with AsyncSessionLocal() as reader:
        current_entitlement = await reader.get(UserEntitlement, held.id)
        current_snapshot = await reader.get(SubscriptionBenefit, snapshot.id)

    assert current_entitlement.status == UserEntitlementStatus.ACTIVE
    assert current_snapshot.status == BenefitStatus.ACTIVE
