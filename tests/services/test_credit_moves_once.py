"""Two nodes retrying the same abandoned grant move the balance once, and the loser reads what the winner wrote."""

from sqlalchemy import func, select

from enums.account import CreditTransactionType
from helpers.db import AsyncSessionLocal
from models.account import CreditTransaction, UserBalance
from services.account import credit_transaction_service, user_balance_service
from tests.services.test_insert_races import blind_once


async def move(db, member, currency, key: str):
    return await credit_transaction_service.move(db, member.id, currency.id, CreditTransactionType.CREDIT, 30, None, key, None, {})


async def balance_of(db, user, currency) -> int:
    """What the account holds of one currency, read from the balance the ledger of that currency explains."""
    held = await user_balance_service.list_for_user(db, user.id)

    return next((row.amount for row in held if row.currency_id == currency.id), 0)


async def test_the_same_key_moves_the_balance_once(db, member, currency):
    first = await move(db, member, currency, "cycle:1")
    second = await move(db, member, currency, "cycle:1")

    assert second.id == first.id
    assert await balance_of(db, member, currency) == 30


async def test_a_balance_another_node_moved_is_read_again_before_it_is_written(db, member, currency):
    """The session holding the balance read it before the lock, and writing that value back is how a movement disappears."""
    await move(db, member, currency, "cycle:0")

    async with AsyncSessionLocal() as elsewhere:
        held = await elsewhere.scalar(select(UserBalance).where(UserBalance.user_id == member.id, UserBalance.currency_id == currency.id))
        held.amount = 100
        await elsewhere.commit()

    transaction = await move(db, member, currency, "cycle:1")

    assert transaction.balance_after == 130
    assert await balance_of(db, member, currency) == 130


async def test_a_node_blind_to_the_winner_still_moves_the_balance_once(db, member, monkeypatch, currency):
    """The read answers nothing while the winner sits between its insert and its commit, which is the only window that matters."""
    first = await move(db, member, currency, "cycle:1")

    blind_once(monkeypatch, credit_transaction_service, "settled_by_key", None)

    second = await move(db, member, currency, "cycle:1")

    assert second.id == first.id
    assert await balance_of(db, member, currency) == 30
    assert await db.scalar(select(func.count()).select_from(CreditTransaction)) == 1
