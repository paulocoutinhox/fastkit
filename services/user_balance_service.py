from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from helpers.db import insert_or_read
from models.currency import Currency
from models.user import User
from models.user_balance import UserBalance
from services.crud_service import CrudService
from services.reach import Reach


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


user_balance_service = UserBalanceService()
