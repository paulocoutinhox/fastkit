from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.purchase import Purchase
from services.crud_service import CrudService


class PurchaseService(CrudService):
    model = Purchase
    search_fields = ("reference", "external_id")
    filter_fields = ("tenant_id", "user_id", "product_id", "integration_id", "status")
    ordering_fields = ("id", "status", "price", "paid_at", "created_at")
    default_ordering = "-id"
    relations = ("tenant", "user", "product")
    label_fields = ("reference",)

    async def list_for_user(self, db: AsyncSession, user_id: int, limit: int, offset: int) -> tuple[int, list[Purchase]]:
        condition = Purchase.user_id == user_id

        total = await db.scalar(select(func.count()).select_from(Purchase).where(condition))
        result = await db.execute(self.base_statement().where(condition).order_by(Purchase.id.desc()).limit(limit).offset(offset))

        return total, list(result.scalars().unique())

    async def find_for_user(self, db: AsyncSession, user_id: int, purchase_id: int) -> Purchase | None:
        """The purchase of this account and no other, because the number in the path is what somebody typed."""
        return await db.scalar(self.base_statement().where(Purchase.id == purchase_id, Purchase.user_id == user_id))

    async def find_by_reference(self, db: AsyncSession, reference: str) -> Purchase | None:
        return await db.scalar(self.base_statement().where(Purchase.reference == reference))

    async def find_by_payment(self, db: AsyncSession, payment_id: str) -> Purchase | None:
        """What a charge names, which is the payment this side stored when the session that opened it settled."""
        return await db.scalar(self.base_statement().where(Purchase.external_id == payment_id))


purchase_service = PurchaseService()
