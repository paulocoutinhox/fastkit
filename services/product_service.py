from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from enums.upload_purpose import UploadPurpose
from helpers.scope import belongs_to_tenant, reaches_tenant
from helpers.validation_error import ValidationError
from models.currency import Currency
from models.entitlement import Entitlement
from models.product import Product
from services.crud_service import CrudService
from services.elsewhere import Elsewhere


class ProductService(CrudService):
    model = Product
    shared = True
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

        # Credits with no currency are never handed over, and a currency with no credits hands over nothing, so the two go together or not at all.
        credits = self.declared(prepared, instance, "credits")
        currency_id = self.declared(prepared, instance, "credits_currency_id")

        if bool(credits) != (currency_id is not None):
            raise ValidationError("error.product-credits-require-currency", "credits_currency_id")

        await self.ensure_reaches(db, Currency, currency_id, tenant_id, "credits_currency_id")

    def reachable(self, tenant_id: int | None):
        return self.base_statement().where(Product.active.is_(True), reaches_tenant(Product.tenant_id, tenant_id))

    async def list_reachable(self, db: AsyncSession, tenant_id: int | None, search: str | None = None) -> list[Product]:
        """A slug is unique inside a brand and among the shared rows, so a brand's product hides the shared one of the same address, which is the one that address opens."""
        result = await db.execute(self.apply_search(self.reachable(tenant_id), search).order_by(*self.search_ordering(search, None), Product.position.asc(), Product.id.asc()))
        found = list(result.scalars().unique())
        owned = {product.slug for product in found if product.tenant_id is not None}

        return [product for product in found if product.tenant_id is not None or product.slug not in owned]

    async def find_reachable(self, db: AsyncSession, tenant_id: int | None, slug: str) -> Product | None:
        """The brand's own row wins over a shared one of the same slug, which is what the listing draws and the checkout sells."""
        return await db.scalar(self.reachable(tenant_id).where(Product.slug == slug).order_by(Product.tenant_id.is_(None), Product.id).limit(1))


product_service = ProductService()
