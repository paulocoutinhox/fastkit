"""Coming back is the same cycle, and starting over is what a plan or an operator says it is."""

import pytest
from sqlalchemy import func, select

from enums.subscription import BenefitType, ResumeDeliveryPolicy, SubscriptionStatus
from models.commerce import UserProduct
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
