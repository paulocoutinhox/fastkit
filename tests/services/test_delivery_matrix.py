"""Every combination the engine has to answer for, and the journeys that cross them."""

from datetime import timedelta

import pytest
from sqlalchemy import func, select

from enums.subscription import BenefitCadence, BenefitGrantStatus, BenefitPolicy, BenefitStatus, BenefitType, IntervalUnit, MissedCyclePolicy, ResumeDeliveryPolicy, SubscriptionStatus, UserEntitlementStatus
from helpers.dates import now
from models.account import CreditTransaction
from models.commerce import UserProduct
from models.subscription import BenefitGrant, Subscription, SubscriptionBenefit, UserEntitlement
from services.delivery import delivery_service
from tests.factories import make_benefit, make_entitlement, make_plan, make_plan_entitlement, make_product, make_subscription

EVERY_TYPE = (BenefitType.ACCESS, BenefitType.CREDIT, BenefitType.PRODUCT)
EVERY_CADENCE = (BenefitCadence.ON_ACTIVATION, BenefitCadence.RECURRING, BenefitCadence.ONCE_PER_USER)
EVERY_MISSED_POLICY = (MissedCyclePolicy.SKIP, MissedCyclePolicy.LATEST_ONLY, MissedCyclePolicy.CATCH_UP)


async def wire(db, tenant, member, *, benefit_type, cadence=BenefitCadence.ON_ACTIVATION, missed=MissedCyclePolicy.SKIP, status=SubscriptionStatus.ACTIVE, trial=BenefitPolicy.ACCESS_ONLY, grace=BenefitPolicy.ACCESS_ONLY, resume=ResumeDeliveryPolicy.SAME_CYCLE):
    plan = await make_plan(db, tenant, trial_benefit_policy=trial, grace_benefit_policy=grace, resume_delivery_policy=resume)
    entitlement = await make_entitlement(db, tenant)
    product = await make_product(db, tenant)

    await make_plan_entitlement(db, plan, entitlement)

    recurring = cadence == BenefitCadence.RECURRING
    target = {BenefitType.ACCESS: "access", BenefitType.CREDIT: "gold", BenefitType.PRODUCT: "handbook"}[benefit_type]

    await make_benefit(db, entitlement, type=benefit_type, target=target, quantity=1, cadence=cadence, missed_cycle_policy=missed, interval_unit=IntervalUnit.MONTH if recurring else None, interval_value=1 if recurring else None, product_id=product.id if benefit_type == BenefitType.PRODUCT else None)

    return await make_subscription(db, tenant, member, plan, status=status)


async def delivered(db, member, benefit_type) -> int:
    if benefit_type == BenefitType.CREDIT:
        return await db.scalar(select(func.count()).select_from(CreditTransaction).where(CreditTransaction.user_id == member.id))

    if benefit_type == BenefitType.PRODUCT:
        return await db.scalar(select(func.count()).select_from(UserProduct).where(UserProduct.user_id == member.id))

    # The entitlement exists from the activation whatever the policy says, so the grant is what measures a delivery.
    statement = (
        select(func.count())
        .select_from(BenefitGrant)
        .join(SubscriptionBenefit, SubscriptionBenefit.id == BenefitGrant.subscription_benefit_id)
        .join(Subscription, Subscription.id == SubscriptionBenefit.subscription_id)
        .where(Subscription.user_id == member.id, SubscriptionBenefit.benefit_type == BenefitType.ACCESS, BenefitGrant.status == BenefitGrantStatus.COMPLETED)
    )

    return await db.scalar(statement)


@pytest.mark.parametrize("benefit_type", EVERY_TYPE)
@pytest.mark.parametrize("status", (SubscriptionStatus.TRIALING, SubscriptionStatus.ACTIVE, SubscriptionStatus.GRACE_PERIOD, SubscriptionStatus.EXPIRED, SubscriptionStatus.REVOKED))
async def test_what_each_kind_of_benefit_delivers_in_each_state(db, tenant, member, benefit_type, status):
    """A paying subscription owes everything, a trial and a grace owe what the plan says, and a dead one owes nothing."""
    subscription = await wire(db, tenant, member, benefit_type=benefit_type, status=status, trial=BenefitPolicy.ACCESS_ONLY, grace=BenefitPolicy.ACCESS_ONLY)

    await delivery_service.activate(db, subscription)

    if status in (SubscriptionStatus.EXPIRED, SubscriptionStatus.REVOKED):
        expected = 0
    elif status == SubscriptionStatus.ACTIVE:
        expected = 1
    else:
        expected = 1 if benefit_type == BenefitType.ACCESS else 0

    assert await delivered(db, member, benefit_type) == expected


@pytest.mark.parametrize("benefit_type", EVERY_TYPE)
@pytest.mark.parametrize("policy", (BenefitPolicy.NONE, BenefitPolicy.ACCESS_ONLY, BenefitPolicy.ALL))
async def test_what_a_trial_delivers_for_every_policy_and_every_kind(db, tenant, member, benefit_type, policy):
    subscription = await wire(db, tenant, member, benefit_type=benefit_type, status=SubscriptionStatus.TRIALING, trial=policy)

    await delivery_service.activate(db, subscription)

    expected = 1 if policy == BenefitPolicy.ALL or (policy == BenefitPolicy.ACCESS_ONLY and benefit_type == BenefitType.ACCESS) else 0

    assert await delivered(db, member, benefit_type) == expected


@pytest.mark.parametrize("benefit_type", EVERY_TYPE)
@pytest.mark.parametrize("policy", (BenefitPolicy.NONE, BenefitPolicy.ACCESS_ONLY, BenefitPolicy.ALL))
async def test_what_a_grace_period_delivers_for_every_policy_and_every_kind(db, tenant, member, benefit_type, policy):
    subscription = await wire(db, tenant, member, benefit_type=benefit_type, status=SubscriptionStatus.GRACE_PERIOD, grace=policy)

    await delivery_service.activate(db, subscription)

    expected = 1 if policy == BenefitPolicy.ALL or (policy == BenefitPolicy.ACCESS_ONLY and benefit_type == BenefitType.ACCESS) else 0

    assert await delivered(db, member, benefit_type) == expected


@pytest.mark.parametrize("benefit_type", EVERY_TYPE)
@pytest.mark.parametrize("cadence", EVERY_CADENCE)
async def test_every_kind_of_benefit_activates_under_every_cadence(db, tenant, member, benefit_type, cadence):
    """A cadence says when it repeats and never whether the first one happens."""
    subscription = await wire(db, tenant, member, benefit_type=benefit_type, cadence=cadence)

    await delivery_service.activate(db, subscription)

    assert await delivered(db, member, benefit_type) == 1


@pytest.mark.parametrize("missed", EVERY_MISSED_POLICY)
async def test_what_each_missed_cycle_policy_pays_for_three_months_of_downtime(db, tenant, member, missed):
    """Three intervals went by with nobody running, and the policy is what says how much of that is owed."""
    subscription = await wire(db, tenant, member, benefit_type=BenefitType.CREDIT, cadence=BenefitCadence.RECURRING, missed=missed)

    await delivery_service.activate(db, subscription)

    for benefit in (await db.execute(select(SubscriptionBenefit).where(SubscriptionBenefit.subscription_id == subscription.id))).scalars():
        benefit.next_grant_at = now() - timedelta(days=95)

    await db.commit()
    await delivery_service.process_due(db)

    after_one_pass = await delivered(db, member, BenefitType.CREDIT)

    # The activation paid one, and what the policy adds on top is what differs.
    assert after_one_pass == (1 if missed == MissedCyclePolicy.SKIP else 2)


@pytest.mark.parametrize("missed", EVERY_MISSED_POLICY)
async def test_a_month_that_merely_came_due_is_paid_whatever_the_policy(db, tenant, member, missed):
    subscription = await wire(db, tenant, member, benefit_type=BenefitType.CREDIT, cadence=BenefitCadence.RECURRING, missed=missed)

    await delivery_service.activate(db, subscription)

    for benefit in (await db.execute(select(SubscriptionBenefit).where(SubscriptionBenefit.subscription_id == subscription.id))).scalars():
        benefit.next_grant_at = now() - timedelta(minutes=1)

    await db.commit()
    await delivery_service.process_due(db)

    assert await delivered(db, member, BenefitType.CREDIT) == 2


@pytest.mark.parametrize("benefit_type", EVERY_TYPE)
async def test_the_life_of_a_subscription_from_the_first_payment_to_the_last(db, tenant, member, benefit_type):
    """Subscribe, be paid, cancel, keep the period, expire, and what was handed over stays handed over."""
    subscription = await wire(db, tenant, member, benefit_type=benefit_type)
    subscription.access_until = now() + timedelta(days=30)
    await db.commit()

    await delivery_service.activate(db, subscription)

    assert await delivered(db, member, benefit_type) == 1

    # Cancelling turns the renewal off and takes nothing away.
    subscription.cancel_at_period_end = True
    await db.commit()
    await delivery_service.expire_subscriptions(db)

    assert subscription.status != SubscriptionStatus.EXPIRED
    assert await delivered(db, member, benefit_type) == 1

    subscription.access_until = now() - timedelta(minutes=1)
    await db.commit()
    await delivery_service.expire_subscriptions(db)

    assert subscription.status == SubscriptionStatus.EXPIRED

    # What ends is the right, and never what it had already given.
    assert await delivered(db, member, benefit_type) == 1

    rights = (await db.execute(select(UserEntitlement).where(UserEntitlement.subscription_id == subscription.id))).scalars().all()

    assert rights and all(right.status == UserEntitlementStatus.EXPIRED for right in rights)


@pytest.mark.parametrize("benefit_type", EVERY_TYPE)
async def test_coming_back_after_expiry_owes_the_same_cycle_and_nothing_more(db, tenant, member, benefit_type):
    subscription = await wire(db, tenant, member, benefit_type=benefit_type, resume=ResumeDeliveryPolicy.SAME_CYCLE)

    await delivery_service.activate(db, subscription)

    subscription.access_until = now() - timedelta(minutes=1)
    await db.commit()
    await delivery_service.expire_subscriptions(db)

    subscription.status = SubscriptionStatus.ACTIVE
    subscription.access_until = now() + timedelta(days=30)
    await db.commit()
    await delivery_service.activate(db, subscription)

    assert await delivered(db, member, benefit_type) == 1


@pytest.mark.parametrize("benefit_type", EVERY_TYPE)
async def test_a_cycle_opened_on_purpose_runs_one_more_of_whatever_the_plan_promises(db, tenant, member, administrator, benefit_type):
    """Every kind runs a second cycle, and what that cycle hands over is what the kind is able to hand over again."""
    subscription = await wire(db, tenant, member, benefit_type=benefit_type)

    await delivery_service.activate(db, subscription)
    await delivery_service.open_new_cycle(db, subscription, administrator)

    assert len((await db.execute(select(BenefitGrant))).scalars().all()) == 2


@pytest.mark.parametrize("benefit_type,expected", [(BenefitType.CREDIT, 2), (BenefitType.PRODUCT, 1)])
async def test_a_second_cycle_pays_a_credit_again_and_never_hands_a_product_over_twice(db, tenant, member, administrator, benefit_type, expected):
    """Credit is a movement and a product is a possession, so one repeats and the other is already held."""
    subscription = await wire(db, tenant, member, benefit_type=benefit_type)

    await delivery_service.activate(db, subscription)
    await delivery_service.open_new_cycle(db, subscription, administrator)

    assert await delivered(db, member, benefit_type) == expected


async def test_a_suspended_subscription_owes_nothing_and_owes_again_when_it_resumes(db, tenant, member):
    subscription = await wire(db, tenant, member, benefit_type=BenefitType.CREDIT, status=SubscriptionStatus.SUSPENDED)
    subscription.benefit_status = BenefitStatus.PAUSED
    await db.commit()

    await delivery_service.activate(db, subscription)

    assert await delivered(db, member, BenefitType.CREDIT) == 0

    subscription.status = SubscriptionStatus.ACTIVE
    subscription.benefit_status = BenefitStatus.ACTIVE
    await db.commit()
    await delivery_service.activate(db, subscription)

    assert await delivered(db, member, BenefitType.CREDIT) == 1


async def test_a_plan_carrying_all_three_kinds_pays_all_three_and_pays_them_once(db, tenant, member, currency):
    plan = await make_plan(db, tenant)
    entitlement = await make_entitlement(db, tenant)
    product = await make_product(db, tenant)

    await make_plan_entitlement(db, plan, entitlement)
    await make_benefit(db, entitlement, type=BenefitType.ACCESS, target="access", quantity=1)
    await make_benefit(db, entitlement, type=BenefitType.CREDIT, target="coins", currency_id=currency.id, quantity=5)
    await make_benefit(db, entitlement, type=BenefitType.PRODUCT, target="handbook", quantity=1, product_id=product.id)

    subscription = await make_subscription(db, tenant, member, plan)

    await delivery_service.activate(db, subscription)
    await delivery_service.activate(db, subscription)

    assert await delivered(db, member, BenefitType.CREDIT) == 1
    assert await delivered(db, member, BenefitType.PRODUCT) == 1
    assert await delivered(db, member, BenefitType.ACCESS) == 1

    grants = (await db.execute(select(BenefitGrant))).scalars().all()

    assert len(grants) == 3
