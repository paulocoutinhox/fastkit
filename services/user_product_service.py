from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.user import User
from models.user_product import UserProduct
from services.crud_service import CrudService
from services.reach import Reach


class UserProductService(CrudService):
    model = UserProduct
    reaches_through = Reach(UserProduct.user_id, User)
    search_fields = ()
    filter_fields = ("user_id", "product_id", "subscription_id")
    ordering_fields = ("id", "granted_at", "created_at")
    default_ordering = "-id"
    relations = ("user", "product")
    label_fields = ("id",)

    async def list_for_user(self, db: AsyncSession, user_id: int) -> list[UserProduct]:
        result = await db.execute(self.base_statement().where(UserProduct.user_id == user_id).order_by(UserProduct.granted_at.desc(), UserProduct.id.desc()))

        return list(result.scalars().unique())

    async def owned_ids(self, db: AsyncSession, user_id: int) -> set[int]:
        """Which products this account holds, read as ids because a catalogue only asks whether, and never what the rows carry."""
        return set((await db.execute(select(UserProduct.product_id).where(UserProduct.user_id == user_id))).scalars())

    async def owned_by(self, db: AsyncSession, user_id: int, product_id: int) -> bool:
        """Whether this account holds this product, which is what says a purchase actually handed something over."""
        return await db.scalar(select(UserProduct.id).where(UserProduct.user_id == user_id, UserProduct.product_id == product_id)) is not None


user_product_service = UserProductService()
