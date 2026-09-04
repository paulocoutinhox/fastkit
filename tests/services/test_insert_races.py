"""The inserts two nodes can reach at once, each proved to hand the loser what the winner wrote."""

import pytest_asyncio
from sqlalchemy import select

from enums.account import CreditTransactionType
from enums.subscription import BenefitType
from models.commerce import UserProduct
from models.subscription import SubscriptionBenefit, UserEntitlement
from services.account import credit_transaction_service
from services.commerce import commerce_service
from services.delivery import delivery_service
from tests.factories import make_benefit, make_entitlement, make_plan, make_plan_entitlement, make_product, make_subscription


def blind_once(monkeypatch, service, name: str, empty) -> list:
    """The read answers nothing once, which is what a node sees while the winner is between its insert and its commit."""
    original = getattr(type(service), name)
    spent = []

    async def read(self, *args, **kwargs):
        if not spent:
            spent.append(True)

            return empty

        return await original(self, *args, **kwargs)

    monkeypatch.setattr(type(service), name, read)

    return spent


@pytest_asyncio.fixture
async def racing(db, tenant, member):
    plan = await make_plan(db, tenant)
    entitlement = await make_entitlement(db, tenant)

    await make_plan_entitlement(db, plan, entitlement)
    await make_benefit(db, entitlement, type=BenefitType.ACCESS, target="access", quantity=1)

    return await make_subscription(db, tenant, member, plan)


async def balance_of(db, user, currency) -> int:
    """What the account holds of one currency, read from the balance the ledger of that currency explains."""
    from services.account import user_balance_service

    held = await user_balance_service.list_for_user(db, user.id)

    return next((row.amount for row in held if row.currency_id == currency.id), 0)


async def test_the_node_that_loses_the_entitlement_is_handed_the_one_that_won(db, racing, monkeypatch):
    """The webhook and the refresh activate the same purchase at once, and a second right would be a second promise."""
    await delivery_service.activate(db, racing)
    blinded = blind_once(monkeypatch, delivery_service, "entitlements_of", {})

    await delivery_service.activate(db, racing)

    assert blinded
    assert len((await db.execute(select(UserEntitlement).where(UserEntitlement.subscription_id == racing.id))).scalars().all()) == 1


async def test_the_node_that_loses_the_snapshot_is_handed_the_one_that_won(db, racing, monkeypatch):
    """Two snapshots of the same benefit would deliver the same cycle under two schedules."""
    await delivery_service.activate(db, racing)
    blinded = blind_once(monkeypatch, delivery_service, "benefits_of", {})

    await delivery_service.activate(db, racing)

    assert blinded
    assert len((await db.execute(select(SubscriptionBenefit).where(SubscriptionBenefit.subscription_id == racing.id))).scalars().all()) == 1


async def test_two_passes_handing_over_the_same_product_leave_one_row(db, tenant, member):
    """A plan delivering and a payment settling can name the same product, and owning it twice is not a thing."""
    product = await make_product(db, tenant)

    first, granted_first = await commerce_service.grant(db, member.id, product.id, "grant-1")
    second, granted_second = await commerce_service.grant(db, member.id, product.id, "grant-2")

    assert granted_first
    assert not granted_second
    assert first.id == second.id
    assert len((await db.execute(select(UserProduct).where(UserProduct.user_id == member.id))).scalars().all()) == 1


async def test_the_credits_of_a_product_are_added_once_however_often_it_is_handed_over(db, tenant, member, currency):
    product = await make_product(db, tenant, credits=100, credits_currency_id=currency.id)

    await commerce_service.grant(db, member.id, product.id, "grant-1")
    await commerce_service.grant(db, member.id, product.id, "grant-2")
    await db.refresh(member)

    assert await balance_of(db, member, currency) == 100


async def test_the_loser_of_a_credit_race_never_moves_the_wallet_twice(db, member, currency):
    """The ledger and the balance move together, so a loser that added would leave a balance no line explains."""
    await credit_transaction_service.move(db, member.id, currency.id, CreditTransactionType.CREDIT, 50, "bonus", "same-key", None, {})
    await credit_transaction_service.move(db, member.id, currency.id, CreditTransactionType.CREDIT, 50, "bonus", "same-key", None, {})
    await db.refresh(member)

    assert await balance_of(db, member, currency) == 50


async def test_a_row_written_between_the_read_and_the_insert_is_the_row_the_loser_is_handed(db, tenant, member, monkeypatch):
    """The look before writing settles the ordinary case, and this is the one it cannot: the winner commits inside the window between them."""
    from helpers.db import AsyncSessionLocal, insert_or_read

    product = await make_product(db, tenant)
    read = select(UserProduct).where(UserProduct.user_id == member.id, UserProduct.product_id == product.id)

    assert await db.scalar(read) is None

    async with AsyncSessionLocal() as winner:
        winner.add(UserProduct(user_id=member.id, product_id=product.id, meta={}))
        await winner.commit()

    # The look before writing is blind exactly once, which is what a node sees while the winner is between its insert and its commit.
    blind_once(monkeypatch, db, "scalar", None)

    settled = await insert_or_read(db, UserProduct(user_id=member.id, product_id=product.id, meta={}), read)
    await db.commit()

    assert settled.id is not None
    assert len((await db.execute(read)).scalars().all()) == 1
