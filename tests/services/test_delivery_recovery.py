from datetime import timedelta

from sqlalchemy import select

from enums.subscription import BenefitGrantStatus, BenefitStatus, BenefitType, SubscriptionStatus, UserEntitlementStatus
from enums.system_log import LogLevel
from helpers.dates import now
from models.commerce import UserProduct
from models.subscription import UserEntitlement
from models.system_log import SystemLog
from services.delivery import ABANDONED_AFTER, MAX_ATTEMPTS, delivery_service
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
    from services.account import user_balance_service

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
