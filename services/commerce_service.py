from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from enums.commerce import SETTLED_PURCHASE_STATUSES
from enums.credit_transaction_type import CreditTransactionType
from enums.purchase_status import PurchaseStatus
from helpers.brand import Brand
from helpers.conflict_error import ConflictError
from helpers.dates import now
from helpers.db import commit, insert_or_read
from models.product import Product
from models.purchase import Purchase
from models.user import User
from models.user_product import UserProduct
from services.credit_transaction_service import credit_transaction_service
from services.user_product_service import user_product_service


class CommerceService:
    """What buying and being given a product both go through, so owning one means the same thing either way."""

    async def grant(self, db: AsyncSession, user_id: int, product_id: int, source_key: str, subscription_id: int | None = None, purchase_id: int | None = None, benefit_grant_id: int | None = None) -> tuple[UserProduct, bool]:
        """Hands the product over once, and answers whether this call is the one that did it."""
        owned = UserProduct(user_id=user_id, product_id=product_id, subscription_id=subscription_id, purchase_id=purchase_id, benefit_grant_id=benefit_grant_id, granted_at=now())
        settled = await insert_or_read(db, owned, select(UserProduct).where(UserProduct.user_id == user_id, UserProduct.product_id == product_id))

        if settled is not owned:
            return settled, False

        product = await db.get(Product, product_id)

        if product.credits and product.credits_currency_id:
            await credit_transaction_service.move(db, user_id, product.credits_currency_id, CreditTransactionType.CREDIT, product.credits, product.name, f"product:{source_key}", benefit_grant_id, {"product_id": product_id})

        await commit(db)

        return settled, True

    async def open_purchase(self, db: AsyncSession, brand: Brand, user: User, product: Product, integration_id: int | None) -> Purchase:
        """The row exists before the buyer leaves, because what a gateway echoes back has to name something this side already wrote."""
        # Owning is one row whatever paid for it, so a second purchase of the same product is money taken for nothing.
        if await user_product_service.owned_by(db, user.id, product.id):
            raise ConflictError("error.product-already-owned")

        purchase = Purchase(tenant_id=brand.id, user_id=user.id, product_id=product.id, integration_id=integration_id, currency=product.currency, price=product.price, status=PurchaseStatus.PENDING)
        db.add(purchase)
        await commit(db)

        return purchase

    async def settle_purchase(self, db: AsyncSession, purchase: Purchase, status: PurchaseStatus, external_id: str | None = None) -> Purchase:
        """What the gateway said about a payment, where paid is the only word that hands the product over."""
        if purchase.status == status:
            return purchase

        # A notice redelivered for days after the money arrived never unsettles it, nothing that left pending ever goes back to waiting, and money that went back is final.
        # A chargeback is not final, because a dispute the merchant wins pays the purchase again.
        if status == PurchaseStatus.PENDING or purchase.status == PurchaseStatus.REFUNDED or (purchase.status in SETTLED_PURCHASE_STATUSES and status not in SETTLED_PURCHASE_STATUSES):
            return purchase

        changes = {"status": status} | ({"external_id": external_id} if external_id else {}) | ({"paid_at": now()} if status == PurchaseStatus.PAID else {})

        # Two notices about one payment cross, so the move is written against the status it was decided on and the one that lost decides again.
        if (await db.execute(update(Purchase).where(Purchase.id == purchase.id, Purchase.status == purchase.status).values(**changes))).rowcount != 1:
            await db.refresh(purchase)

            return await self.settle_purchase(db, purchase, status, external_id)

        if status == PurchaseStatus.PAID:
            await self.grant(db, purchase.user_id, purchase.product_id, purchase.reference, purchase_id=purchase.id)

        await commit(db)

        return purchase


commerce_service = CommerceService()
