"""A benefit says when the engine grants next, and one it never grants says nothing at all."""

from sqlalchemy import select

from enums.subscription import BenefitCadence, BenefitStatus, BenefitType, IntervalUnit, SubscriptionStatus
from models.subscription import SubscriptionBenefit
from services.delivery import delivery_service
from tests.factories import make_benefit, make_entitlement, make_plan, make_plan_entitlement, make_subscription


async def snapshot_of(db, tenant, member, **benefit):
    entitlement = await make_entitlement(db, tenant)
    plan = await make_plan(db, tenant)
    await make_plan_entitlement(db, plan, entitlement)
    await make_benefit(db, entitlement, **benefit)

    subscription = await make_subscription(db, tenant, member, plan)
    await delivery_service.activate(db, subscription)

    return subscription, (await db.execute(select(SubscriptionBenefit).where(SubscriptionBenefit.subscription_id == subscription.id))).scalars().one()


async def test_a_benefit_the_engine_never_grants_carries_no_next_grant(db, tenant, member):
    _, benefit = await snapshot_of(db, tenant, member, cadence=BenefitCadence.ON_ACTIVATION, grant_on_activation=False, type=BenefitType.ACCESS)

    assert benefit.next_grant_at is None


async def test_a_benefit_the_activation_grants_says_when(db, tenant, member):
    subscription, benefit = await snapshot_of(db, tenant, member, cadence=BenefitCadence.ON_ACTIVATION, grant_on_activation=True)

    assert benefit.anchor_at == subscription.started_at


async def test_a_recurring_benefit_says_when(db, tenant, member):
    _, benefit = await snapshot_of(db, tenant, member, cadence=BenefitCadence.RECURRING, interval_unit=IntervalUnit.MONTH, interval_value=1)

    assert benefit.next_grant_at is not None


async def test_the_same_benefit_reads_the_same_after_the_subscription_came_back(db, tenant, member):
    """It ended and revived, and a date that reappeared only for some cadences is the same benefit answering two ways."""
    subscription, benefit = await snapshot_of(db, tenant, member, cadence=BenefitCadence.ON_ACTIVATION, grant_on_activation=False, type=BenefitType.ACCESS)
    fresh = benefit.next_grant_at

    await delivery_service.end_benefits(db, subscription)
    await db.commit()

    subscription.status = SubscriptionStatus.ACTIVE
    await delivery_service.activate(db, subscription)
    await db.refresh(benefit)

    assert benefit.status == BenefitStatus.ACTIVE
    assert benefit.next_grant_at == fresh
