from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from enums.account import CreditTransactionType
from enums.commerce import SETTLED_PURCHASE_STATUSES, PurchaseStatus
from enums.upload import UploadPurpose
from helpers.brand import Brand
from helpers.dates import now
from helpers.db import commit, insert_or_read
from helpers.scope import belongs_to_tenant, reaches_tenant
from models.commerce import Product, Purchase, UserProduct
from models.subscription import Entitlement
from models.user import User
from services.account import credit_transaction_service
from services.crud import CrudService, Elsewhere, Reach


class ProductService(CrudService):
    model = Product
    search_fields = ("slug",)
    text_search_fields = ("name",)
    filter_fields = ("tenant_id", "entitlement_id", "featured", "active")

    # A plan hands over what its own brand reaches, so an entitlement of one brand never points at the product of another.
    # Naming one that is not there answers nothing, because a null scope reads as the shared rows and would offer the whole shared catalogue instead.
    filters_elsewhere = {"entitlement_id": Elsewhere(Entitlement.id, lambda value: and_(select(Entitlement.id).where(Entitlement.id == value).exists(), reaches_tenant(Product.tenant_id, select(Entitlement.tenant_id).where(Entitlement.id == value).scalar_subquery())))}

    ordering_fields = ("id", "name", "slug", "price", "position", "created_at")
    default_ordering = "position"
    relations = ("tenant", "credits_currency")
    label_fields = ("name",)
    file_fields = {"image": UploadPurpose.PRODUCT_IMAGE, "file": UploadPurpose.PRODUCT_FILE}
    markup_fields = ("description",)
    position_field = "position"

    async def prepare(self, data: dict, instance) -> dict:
        prepared = self.apply_slug(dict(data), instance, "slug", ("name",), "product")

        if prepared.get("currency"):
            prepared["currency"] = prepared["currency"].upper()

        return prepared

    async def validate(self, db: AsyncSession, data: dict, instance) -> None:
        prepared = await self.prepare(data, instance)
        tenant_id = self.declared(prepared, instance, "tenant_id")

        await self.ensure_unique(db, Product.slug, prepared.get("slug"), "error.slug-already-used", "slug", instance, belongs_to_tenant(Product.tenant_id, tenant_id))

    def reachable(self, tenant_id: int | None):
        return self.base_statement().where(Product.active.is_(True), reaches_tenant(Product.tenant_id, tenant_id))

    async def list_reachable(self, db: AsyncSession, tenant_id: int | None, search: str | None = None) -> list[Product]:
        result = await db.execute(self.apply_search(self.reachable(tenant_id), search).order_by(*self.search_ordering(search, None), Product.position.asc(), Product.id.asc()))

        return list(result.scalars().unique())

    async def find_reachable(self, db: AsyncSession, tenant_id: int | None, slug: str) -> Product | None:
        return await db.scalar(self.reachable(tenant_id).where(Product.slug == slug))


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

    async def owned_by(self, db: AsyncSession, user_id: int, product_id: int) -> bool:
        """Whether this account holds this product, which is what says a purchase actually handed something over."""
        return await db.scalar(select(UserProduct.id).where(UserProduct.user_id == user_id, UserProduct.product_id == product_id)) is not None


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
        purchase = Purchase(tenant_id=brand.id, user_id=user.id, product_id=product.id, integration_id=integration_id, currency=product.currency, price=product.price, status=PurchaseStatus.PENDING)
        db.add(purchase)
        await commit(db)

        return purchase

    async def settle_purchase(self, db: AsyncSession, purchase: Purchase, status: PurchaseStatus, external_id: str | None = None) -> Purchase:
        """What the gateway said about a payment, where paid is the only word that hands the product over."""
        if purchase.status == status:
            return purchase

        # The notice that opened a delayed payment is redelivered for days after the money arrived, and it never unsettles it.
        if purchase.status in SETTLED_PURCHASE_STATUSES and status not in SETTLED_PURCHASE_STATUSES:
            return purchase

        purchase.status = status

        if external_id:
            purchase.external_id = external_id

        if status != PurchaseStatus.PAID:
            await commit(db)

            return purchase

        purchase.paid_at = now()
        await self.grant(db, purchase.user_id, purchase.product_id, purchase.reference, purchase_id=purchase.id)
        await commit(db)

        return purchase


product_service = ProductService()
purchase_service = PurchaseService()
user_product_service = UserProductService()
commerce_service = CommerceService()
