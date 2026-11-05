import secrets

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from enums.credit_transaction_type import CreditTransactionType
from helpers.db import commit
from helpers.validation_error import ValidationError
from models.base import BIG_INTEGER_MAX
from models.credit_transaction import CreditTransaction
from models.currency import Currency
from models.user import User
from services.crud_service import CrudService
from services.reach import Reach
from services.upload import owner_of
from services.upload_service import upload_service
from services.user_balance_service import user_balance_service

# The type is what an audit reads, so it decides the direction — and an adjustment is the one that exists to carry its own.
DIRECTIONS = {CreditTransactionType.CREDIT: 1, CreditTransactionType.DEBIT: -1, CreditTransactionType.REVERSAL: -1, CreditTransactionType.ADJUSTMENT: None}


def signed_amount(transaction_type: CreditTransactionType, amount: int) -> int:
    """A movement named credit never takes from the balance, and one named reversal never adds to it."""
    direction = DIRECTIONS[transaction_type]

    if direction is None:
        return amount

    # A directed movement carries a magnitude, and reading a negative one as its opposite writes the entry nobody asked for.
    if amount < 0:
        raise ValidationError("error.amount-must-be-positive", "amount")

    return direction * amount


class CreditTransactionService(CrudService):
    model = CreditTransaction
    reaches_through = Reach(CreditTransaction.user_id, User)
    search_fields = ("idempotency_key",)
    text_search_fields = ("description",)
    filter_fields = ("user_id", "currency_id", "type", "benefit_grant_id")
    ordering_fields = ("id", "amount", "created_at")
    default_ordering = "-id"
    relations = ("user", "currency")
    label_fields = ("idempotency_key",)

    async def create(self, db: AsyncSession, data: dict, operator=None):
        """A manual entry from the admin moves the balance through the same path a delivery does, so the balance and the ledger never drift apart."""
        await self.ensure_references_are_reachable(db, data, operator)

        transaction = await self.move(db, data["user_id"], data["currency_id"], data["type"], data["amount"], data.get("description"), secrets.token_urlsafe(24), None, data.get("meta") or {})

        await upload_service.mention(db, owner_of(transaction), self.mentioned(transaction))
        await commit(db)

        return await self.get(db, transaction.id, operator)

    def settled_statement(self, idempotency_key: str):
        return select(CreditTransaction).where(CreditTransaction.idempotency_key == idempotency_key)

    async def settled_by_key(self, db: AsyncSession, idempotency_key: str) -> CreditTransaction | None:
        return await db.scalar(self.settled_statement(idempotency_key))

    async def move(self, db: AsyncSession, user_id: int, currency_id: int, transaction_type: CreditTransactionType, amount: int, description: str | None, idempotency_key: str, benefit_grant_id: int | None, meta: dict) -> CreditTransaction:
        existing = await self.settled_by_key(db, idempotency_key)

        if existing is not None:
            return existing

        # Both keys were checked to name a row before this, by the manual entry and by the engine alike.
        user = await db.get(User, user_id)
        currency = await db.get(Currency, currency_id)

        # A currency of another brand is one the account cannot hold, whoever asked for the move.
        if currency.tenant_id not in (None, user.tenant_id):
            raise ValidationError("error.related-not-found", "currency_id")

        held = await user_balance_service.held(db, user_id, currency_id)
        settled = await self.settled_by_key(db, idempotency_key)

        if settled is not None:
            return settled

        signed = signed_amount(CreditTransactionType(transaction_type), amount)
        balance = held.amount + signed

        if balance < 0:
            raise ValidationError("error.insufficient-credits", "amount")

        # A balance past what the column holds overflows inside the driver, the same way one below zero would be a balance nobody has.
        if balance > BIG_INTEGER_MAX:
            raise ValidationError("error.balance-out-of-range", "amount")

        transaction = CreditTransaction(user_id=user_id, currency_id=currency_id, benefit_grant_id=benefit_grant_id, type=transaction_type, amount=signed, balance_after=balance, idempotency_key=idempotency_key, description=description, meta=meta)

        db.add(transaction)
        held.amount = balance
        await self.persist(db)

        return transaction

    async def list_for_user(self, db: AsyncSession, user_id: int, limit: int, offset: int) -> tuple[int, list[CreditTransaction]]:
        condition = CreditTransaction.user_id == user_id

        total = await db.scalar(select(func.count()).select_from(CreditTransaction).where(condition))
        result = await db.execute(self.base_statement().where(condition).order_by(CreditTransaction.id.desc()).limit(limit).offset(offset))

        return total, list(result.scalars().unique())


credit_transaction_service = CreditTransactionService()
