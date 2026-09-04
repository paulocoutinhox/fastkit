"""What a subscription owes is either delivered or written down as not delivered, and never neither."""

from datetime import timedelta

import pytest_asyncio
from sqlalchemy import func, select

from enums.subscription import ELIGIBLE_SUBSCRIPTION_STATUSES, BenefitCadence, BenefitGrantStatus, BenefitStatus, BenefitType, IntervalUnit, SubscriptionStatus, UserEntitlementStatus
from helpers.dates import now
from jobs.subscription import run_subscription_cycle
from models.account import CreditTransaction, UserBalance
from models.commerce import UserProduct
from models.subscription import Benefit, BenefitGrant, PlanEntitlement, Subscription, SubscriptionBenefit, UserEntitlement
from services.delivery import delivery_service
from tests.factories import make_benefit, make_entitlement, make_plan, make_plan_entitlement, make_product, make_subscription


async def nothing_is_owed(db) -> list[str]:
    """Every way an obligation can go missing, asked of the database itself."""
    alive = Subscription.status.in_(ELIGIBLE_SUBSCRIPTION_STATUSES)
    found = []

    promising = select(PlanEntitlement.plan_id)
    without_rights = (await db.execute(select(Subscription.id).where(alive, Subscription.plan_id.in_(promising), ~Subscription.id.in_(select(UserEntitlement.subscription_id))))).scalars().all()
    found += [f"subscription {one} promises rights and holds none" for one in without_rights]

    promised = select(Benefit.entitlement_id).where(Benefit.active.is_(True))
    without_snapshot = (await db.execute(select(Subscription.id).join(UserEntitlement, UserEntitlement.subscription_id == Subscription.id).where(alive, UserEntitlement.entitlement_id.in_(promised), ~Subscription.id.in_(select(SubscriptionBenefit.subscription_id))))).scalars().all()
    found += [f"subscription {one} has a right that promises a benefit and no snapshot" for one in without_snapshot]

    never = (await db.execute(select(SubscriptionBenefit.id).join(Subscription, Subscription.id == SubscriptionBenefit.subscription_id).where(alive, SubscriptionBenefit.status == BenefitStatus.ACTIVE, SubscriptionBenefit.grant_on_activation.is_(True), SubscriptionBenefit.last_grant_at.is_(None)))).scalars().all()
    found += [f"benefit {one} grants on activation and never did" for one in never]

    stalled = (
        (await db.execute(select(SubscriptionBenefit.id).join(Subscription, Subscription.id == SubscriptionBenefit.subscription_id).where(alive, SubscriptionBenefit.status == BenefitStatus.ACTIVE, SubscriptionBenefit.cadence == BenefitCadence.RECURRING, SubscriptionBenefit.next_grant_at.is_(None)))).scalars().all()
    )
    found += [f"benefit {one} recurs and has no next cycle" for one in stalled]

    stuck = (await db.execute(select(BenefitGrant.grant_key).where(BenefitGrant.status == BenefitGrantStatus.PROCESSING))).scalars().all()
    found += [f"grant {one} is still processing" for one in stuck]

    orphan_right = (await db.execute(select(UserEntitlement.id).join(Subscription, Subscription.id == UserEntitlement.subscription_id).where(UserEntitlement.status == UserEntitlementStatus.ACTIVE, ~alive))).scalars().all()
    found += [f"right {one} is open on a subscription that is not" for one in orphan_right]

    closed_right = (await db.execute(select(UserEntitlement.id).join(Subscription, Subscription.id == UserEntitlement.subscription_id).where(UserEntitlement.status == UserEntitlementStatus.EXPIRED, alive))).scalars().all()
    found += [f"right {one} is closed on a subscription that is alive" for one in closed_right]

    twice = (await db.execute(select(BenefitGrant.subscription_benefit_id, BenefitGrant.cycle_key).group_by(BenefitGrant.subscription_benefit_id, BenefitGrant.cycle_key).having(func.count() > 1))).all()
    found += [f"benefit {one} delivered cycle {cycle} twice" for one, cycle in twice]

    return found


@pytest_asyncio.fixture
async def owing(db, tenant, member):
    """A plan that promises one of everything, so every kind of obligation is on the table."""
    plan = await make_plan(db, tenant)
    entitlement = await make_entitlement(db, tenant)
    product = await make_product(db, tenant)

    await make_plan_entitlement(db, plan, entitlement)

    await make_benefit(db, entitlement, type=BenefitType.ACCESS, target="access", quantity=1)
    await make_benefit(db, entitlement, type=BenefitType.CREDIT, target="gold", quantity=5, cadence=BenefitCadence.RECURRING, interval_unit=IntervalUnit.MONTH, interval_value=1)
    await make_benefit(db, entitlement, type=BenefitType.PRODUCT, target="handbook", quantity=1, product_id=product.id)

    return await make_subscription(db, tenant, member, plan)


async def test_nothing_is_owed_after_an_activation(db, owing):
    await delivery_service.activate(db, owing)

    assert await nothing_is_owed(db) == []


async def test_nothing_is_owed_after_a_cycle_comes_due(db, owing):
    await delivery_service.activate(db, owing)

    for benefit in (await db.execute(select(SubscriptionBenefit).where(SubscriptionBenefit.cadence == BenefitCadence.RECURRING))).scalars():
        benefit.next_grant_at = now() - timedelta(minutes=1)

    await db.commit()
    await delivery_service.process_due(db)

    assert await nothing_is_owed(db) == []


async def test_nothing_is_owed_after_the_subscription_ends(db, owing):
    await delivery_service.activate(db, owing)

    owing.access_until = now() - timedelta(days=1)
    await db.commit()
    await delivery_service.expire_subscriptions(db)

    assert await nothing_is_owed(db) == []


async def test_nothing_is_owed_after_it_comes_back(db, owing):
    await delivery_service.activate(db, owing)

    owing.access_until = now() - timedelta(days=1)
    await db.commit()
    await delivery_service.expire_subscriptions(db)

    # The provider brings a subscription back the way `carry` writes it, which is both the status and the benefit status.
    owing.status = SubscriptionStatus.ACTIVE
    owing.benefit_status = BenefitStatus.ACTIVE
    owing.access_until = now() + timedelta(days=30)
    await db.commit()
    await delivery_service.activate(db, owing)

    assert await nothing_is_owed(db) == []


async def test_the_check_notices_an_obligation_that_went_missing(db, owing):
    """A check that never fires proves nothing, so one is made to fire on purpose."""
    await delivery_service.activate(db, owing)

    benefit = (await db.execute(select(SubscriptionBenefit).where(SubscriptionBenefit.cadence == BenefitCadence.RECURRING))).scalars().first()
    benefit.next_grant_at = None
    await db.commit()

    assert [line for line in await nothing_is_owed(db) if "no next cycle" in line]


async def test_the_whole_pass_run_again_and_again_moves_nothing(db, tenant, member, currency):
    """The cron fires every five minutes forever, so the pass has to be something that can run twice."""

    async def counted():
        rows = {model.__name__: await db.scalar(select(func.count()).select_from(model)) for model in (BenefitGrant, CreditTransaction, UserProduct, UserEntitlement, SubscriptionBenefit)}

        return rows | {"balance": await db.scalar(select(UserBalance.amount)) or 0}

    entitlement = await make_entitlement(db, tenant)
    plan = await make_plan(db, tenant)
    await make_plan_entitlement(db, plan, entitlement)
    product = await make_product(db, tenant)

    await make_benefit(db, entitlement, type=BenefitType.CREDIT, target="coins", quantity=50, currency_id=currency.id, cadence=BenefitCadence.RECURRING, interval_unit=IntervalUnit.MONTH, interval_value=1)
    await make_benefit(db, entitlement, type=BenefitType.PRODUCT, target="handbook", product_id=product.id, cadence=BenefitCadence.ON_ACTIVATION)
    await make_benefit(db, entitlement, type=BenefitType.ACCESS, target="member", cadence=BenefitCadence.ON_ACTIVATION)

    await delivery_service.activate(db, await make_subscription(db, tenant, member, plan))
    await db.commit()

    settled = await counted()

    for _ in range(3):
        await run_subscription_cycle(db)

    assert settled["BenefitGrant"] == 3
    assert settled["balance"] == 50
    assert await counted() == settled
