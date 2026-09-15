"""Coming back is the same cycle, and starting over is what a plan or an operator says it is."""

from datetime import timedelta

import pytest
from sqlalchemy import func, select

from enums.subscription import BenefitCadence, BenefitStatus, BenefitType, IntervalUnit, MissedCyclePolicy, ResumeDeliveryPolicy, SubscriptionStatus
from helpers.dates import add_interval, now
from models.commerce import UserProduct
from models.subscription import SubscriptionBenefit
from services.delivery import delivery_service
from tests.factories import make_benefit, make_entitlement, make_plan, make_plan_entitlement, make_product, make_subscription


@pytest.fixture
async def programme(currency, db, tenant, member):
    entitlement = await make_entitlement(db, tenant)
    product = await make_product(db, tenant)

    await make_benefit(db, entitlement, type=BenefitType.CREDIT, target="coins", currency_id=currency.id, quantity=10)
    await make_benefit(db, entitlement, type=BenefitType.PRODUCT, target="handbook", quantity=1, product_id=product.id)

    return {"entitlement": entitlement, "product": product}


async def subscribe(db, tenant, member, programme, policy):
    plan = await make_plan(db, tenant, resume_delivery_policy=policy)
    await make_plan_entitlement(db, plan, programme["entitlement"])

    return plan, await make_subscription(db, tenant, member, plan)


async def owned(db, member) -> int:
    return await db.scalar(select(func.count()).select_from(UserProduct).where(UserProduct.user_id == member.id))


async def balance_of(db, user, currency) -> int:
    """What the account holds of one currency, read from the balance the ledger of that currency explains."""
    from services.account import user_balance_service

    held = await user_balance_service.list_for_user(db, user.id)

    return next((row.amount for row in held if row.currency_id == currency.id), 0)


async def test_a_subscription_delivers_its_first_cycle(db, tenant, member, programme, currency):
    _, subscription = await subscribe(db, tenant, member, programme, ResumeDeliveryPolicy.SAME_CYCLE)
    await delivery_service.activate(db, subscription)
    await db.refresh(member)

    assert await balance_of(db, member, currency) == 10
    assert await owned(db, member) == 1


async def test_paying_a_late_bill_and_coming_back_delivers_nothing_new(db, tenant, member, programme, currency):
    """The common case: the bill was late, access dropped, the bill was paid. it is a suspension and not a purchase."""
    _, subscription = await subscribe(db, tenant, member, programme, ResumeDeliveryPolicy.SAME_CYCLE)
    await delivery_service.activate(db, subscription)

    subscription.status = SubscriptionStatus.SUSPENDED
    await db.commit()

    subscription.status = SubscriptionStatus.ACTIVE
    await db.commit()
    await delivery_service.activate(db, subscription)
    await db.refresh(member)

    assert await balance_of(db, member, currency) == 10


async def test_releasing_a_cycle_moves_every_benefit_of_the_subscription_forward(db, tenant, member, programme):
    _, subscription = await subscribe(db, tenant, member, programme, ResumeDeliveryPolicy.SAME_CYCLE)
    await delivery_service.activate(db, subscription)

    assert await delivery_service.release_cycle(db, subscription) == 2


async def test_a_released_cycle_delivers_again(db, tenant, member, programme, currency):
    _, subscription = await subscribe(db, tenant, member, programme, ResumeDeliveryPolicy.SAME_CYCLE)
    await delivery_service.activate(db, subscription)
    await delivery_service.release_cycle(db, subscription)
    await delivery_service.activate(db, subscription)
    await db.refresh(member)

    assert await balance_of(db, member, currency) == 20


async def test_what_the_account_already_owns_is_never_handed_over_twice(db, tenant, member, programme):
    """A product is the account's for good, so a fresh cycle finds it already held instead of writing a second row."""
    _, subscription = await subscribe(db, tenant, member, programme, ResumeDeliveryPolicy.SAME_CYCLE)
    await delivery_service.activate(db, subscription)
    await delivery_service.release_cycle(db, subscription)
    await delivery_service.activate(db, subscription)

    assert await owned(db, member) == 1


async def test_an_operator_forcing_a_new_cycle_delivers_and_is_written_down(db, tenant, member, administrator, programme, currency):
    from enums.system_log import LogCategory
    from models.system_log import SystemLog

    _, subscription = await subscribe(db, tenant, member, programme, ResumeDeliveryPolicy.SAME_CYCLE)
    await delivery_service.activate(db, subscription)

    await delivery_service.open_new_cycle(db, subscription, administrator)
    await db.refresh(member)

    assert await balance_of(db, member, currency) == 20

    entry = (await db.execute(select(SystemLog).where(SystemLog.category == LogCategory.PURCHASE).order_by(SystemLog.id.desc()))).scalars().first()

    assert entry.meta["operator_id"] == administrator.id
    assert entry.meta["subscription_id"] == subscription.id


async def test_the_route_that_forces_a_cycle_answers_only_to_an_administrator(client, member_headers, db, tenant, member, programme):
    _, subscription = await subscribe(db, tenant, member, programme, ResumeDeliveryPolicy.SAME_CYCLE)

    assert (await client.post(f"/api/subscriptions/{subscription.id}/new-cycle", headers=member_headers)).status_code == 403


async def test_the_route_that_forces_a_cycle_delivers_for_an_administrator(client, admin_headers, db, tenant, member, programme):
    _, subscription = await subscribe(db, tenant, member, programme, ResumeDeliveryPolicy.SAME_CYCLE)
    await delivery_service.activate(db, subscription)

    response = await client.post(f"/api/subscriptions/{subscription.id}/new-cycle", headers=admin_headers)

    assert response.status_code == 200
    assert response.json()["granted"] == 2


@pytest.mark.parametrize("policy", ["catch-up", "latest-only", "skip"])
def test_coming_back_after_a_lapse_owes_the_cycle_it_lands_in_and_none_of_the_ones_before(policy):
    """A lapse is not downtime of the engine, so `catch-up` would otherwise pay every month nobody paid for, one per pass."""
    lapsed = now() - timedelta(days=200)
    benefit = SubscriptionBenefit(status=BenefitStatus.ENDED, cadence=BenefitCadence.RECURRING, interval_unit=IntervalUnit.MONTH, interval_value=1, missed_cycle_policy=MissedCyclePolicy(policy), last_grant_at=lapsed, next_grant_at=None)

    delivery_service.resume(benefit, lapsed)

    assert benefit.next_grant_at <= now() < add_interval(benefit.next_grant_at, IntervalUnit.MONTH, 1)
    assert delivery_service.resolve_due_slot(benefit, now()) == benefit.next_grant_at, "one slot is due, and it is the one this month"


def test_coming_back_inside_the_cycle_it_left_owes_nothing_until_the_next_one():
    granted = now() - timedelta(days=3)
    benefit = SubscriptionBenefit(status=BenefitStatus.ENDED, cadence=BenefitCadence.RECURRING, interval_unit=IntervalUnit.MONTH, interval_value=1, last_grant_at=granted, next_grant_at=None)

    delivery_service.resume(benefit, granted)

    assert benefit.next_grant_at > now()
