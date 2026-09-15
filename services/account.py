import secrets

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from enums.account import CreditTransactionType
from helpers.db import insert_or_read
from helpers.errors import ValidationError
from helpers.scope import reaches_tenant
from models.account import CreditTransaction, Currency, UserBalance
from models.base import BIG_INTEGER_MAX
from models.user import User
from services.crud import CrudService, Reach

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


class CurrencyService(CrudService):
    model = Currency
    search_fields = ("code",)
    text_search_fields = ("name",)
    filter_fields = ("tenant_id", "active")
    ordering_fields = ("id", "code", "name", "position", "created_at")
    default_ordering = "position"
    relations = ("tenant",)
    label_fields = ("name",)
    position_field = "position"

    async def prepare(self, data: dict, instance) -> dict:
        return self.apply_slug(dict(data), instance, "code", ("name",), "currency")

    async def validate(self, db: AsyncSession, data: dict, instance) -> None:
        prepared = await self.prepare(data, instance)
        tenant_id = self.declared(prepared, instance, "tenant_id")

        await self.ensure_unique(db, Currency.code, prepared.get("code"), "error.code-already-used", "code", instance, Currency.tenant_id == tenant_id)

    async def list_reachable(self, db: AsyncSession, tenant_id: int | None) -> list[Currency]:
        statement = self.base_statement().where(Currency.active.is_(True), reaches_tenant(Currency.tenant_id, tenant_id)).order_by(Currency.position.asc(), Currency.id.asc())

        return list((await db.execute(statement)).scalars().unique())


class UserBalanceService(CrudService):
    model = UserBalance
    reaches_through = Reach(UserBalance.user_id, User)
    search_fields = ()
    filter_fields = ("user_id", "currency_id")
    ordering_fields = ("id", "amount", "created_at")
    default_ordering = "-id"
    relations = ("user", "currency")
    label_fields = ("id",)

    async def list_for_user(self, db: AsyncSession, user_id: int) -> list[UserBalance]:
        statement = self.base_statement().join(Currency, Currency.id == UserBalance.currency_id).where(UserBalance.user_id == user_id).order_by(Currency.position.asc(), Currency.id.asc())

        return list((await db.execute(statement)).scalars().unique())

    async def held(self, db: AsyncSession, user_id: int, currency_id: int) -> UserBalance:
        """The row an account holds one currency in, locked for the movement about to be written on top of it."""
        row = UserBalance(user_id=user_id, currency_id=currency_id, amount=0)
        read = select(UserBalance).where(UserBalance.user_id == user_id, UserBalance.currency_id == currency_id)

        await insert_or_read(db, row, read)

        # The lock is worth nothing without the reread: a row the session already holds answers what it read before, and the balance would be one movement old.
        return await db.scalar(read.with_for_update().execution_options(populate_existing=True))


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

    async def create(self, db: AsyncSession, data: dict):
        """A manual entry from the admin moves the balance through the same path a delivery does, so the balance and the ledger never drift apart."""
        transaction = await self.move(db, data["user_id"], data["currency_id"], data["type"], data["amount"], data.get("description"), secrets.token_urlsafe(24), None, data.get("meta") or {})

        return await self.get(db, transaction.id)

    def settled_statement(self, idempotency_key: str):
        return select(CreditTransaction).where(CreditTransaction.idempotency_key == idempotency_key)

    async def settled_by_key(self, db: AsyncSession, idempotency_key: str) -> CreditTransaction | None:
        return await db.scalar(self.settled_statement(idempotency_key))

    async def move(self, db: AsyncSession, user_id: int, currency_id: int, transaction_type: CreditTransactionType, amount: int, description: str | None, idempotency_key: str, benefit_grant_id: int | None, meta: dict) -> CreditTransaction:
        existing = await self.settled_by_key(db, idempotency_key)

        if existing is not None:
            return existing

        if await db.get(User, user_id) is None:
            raise ValidationError("error.related-not-found", "user_id")

        if await db.get(Currency, currency_id) is None:
            raise ValidationError("error.related-not-found", "currency_id")

        held = await user_balance_service.held(db, user_id, currency_id)
        signed = signed_amount(CreditTransactionType(transaction_type), amount)
        balance = held.amount + signed

        if balance < 0:
            raise ValidationError("error.insufficient-credits", "amount")

        # A balance past what the column holds overflows inside the driver, the same way one below zero would be a balance nobody has.
        if balance > BIG_INTEGER_MAX:
            raise ValidationError("error.balance-out-of-range", "amount")

        transaction = CreditTransaction(user_id=user_id, currency_id=currency_id, benefit_grant_id=benefit_grant_id, type=transaction_type, amount=signed, balance_after=balance, idempotency_key=idempotency_key, description=description, meta=meta)

        # The balance moves only for the node that wrote the entry, so a loser never adds a balance the ledger has no line for.
        settled = await insert_or_read(db, transaction, self.settled_statement(idempotency_key))

        if settled is not transaction:
            return settled

        held.amount = balance
        await self.persist(db)

        return transaction

    async def list_for_user(self, db: AsyncSession, user_id: int, limit: int, offset: int) -> tuple[int, list[CreditTransaction]]:
        condition = CreditTransaction.user_id == user_id

        total = await db.scalar(select(func.count()).select_from(CreditTransaction).where(condition))
        result = await db.execute(self.base_statement().where(condition).order_by(CreditTransaction.id.desc()).limit(limit).offset(offset))

        return total, list(result.scalars().unique())


currency_service = CurrencyService()
user_balance_service = UserBalanceService()
credit_transaction_service = CreditTransactionService()
