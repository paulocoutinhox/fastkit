from sqlalchemy.ext.asyncio import AsyncSession

from enums.user import PANEL_ROLES
from helpers import brand
from helpers.brand import Brand
from models.app_event import AppEvent
from models.banner import Banner
from models.benefit import Benefit
from models.benefit_grant import BenefitGrant
from models.content import Content
from models.credit_transaction import CreditTransaction
from models.currency import Currency
from models.entitlement import Entitlement
from models.external_product import ExternalProduct
from models.gallery import Gallery
from models.gallery_photo import GalleryPhoto
from models.integration import Integration
from models.plan import Plan
from models.plan_entitlement import PlanEntitlement
from models.product import Product
from models.purchase import Purchase
from models.subscription import Subscription
from models.subscription_benefit import SubscriptionBenefit
from models.system_log import SystemLog
from models.tenant import Tenant
from models.user import User
from models.user_address import UserAddress
from models.user_balance import UserBalance
from models.user_entitlement import UserEntitlement
from models.user_product import UserProduct
from models.webhook_event import WebhookEvent
from services.crud_service import CrudService
from services.dependent import Dependent

# A tenant owns everything scoped to it, and this order keeps a restricted reference from firing before the row holding it is gone.
TENANT_DEPENDENTS = (
    Dependent(Subscription, "tenant_id", dependents=(Dependent(SubscriptionBenefit, "subscription_id", dependents=(Dependent(BenefitGrant, "subscription_benefit_id"),)), Dependent(UserEntitlement, "subscription_id"))),
    Dependent(User, "tenant_id", dependents=(Dependent(UserAddress, "user_id"), Dependent(UserProduct, "user_id"), Dependent(Purchase, "user_id"), Dependent(CreditTransaction, "user_id"), Dependent(UserBalance, "user_id"), Dependent(AppEvent, "user_id"))),
    Dependent(Integration, "tenant_id", dependents=(Dependent(WebhookEvent, "integration_id"), Dependent(ExternalProduct, "integration_id"))),
    Dependent(Entitlement, "tenant_id", dependents=(Dependent(Benefit, "entitlement_id"), Dependent(PlanEntitlement, "entitlement_id"))),
    Dependent(Plan, "tenant_id", dependents=(Dependent(PlanEntitlement, "plan_id"),)),
    Dependent(Product, "tenant_id"),
    Dependent(Currency, "tenant_id"),
    Dependent(Gallery, "tenant_id", dependents=(Dependent(GalleryPhoto, "gallery_id"),)),
    Dependent(Content, "tenant_id"),
    Dependent(Banner, "tenant_id"),
    Dependent(AppEvent, "tenant_id"),
    Dependent(SystemLog, "tenant_id"),
)


class TenantService(CrudService):
    model = Tenant
    system_wide = True
    lookup_roles = PANEL_ROLES
    search_fields = ("code", "domain")
    text_search_fields = ("name",)
    filter_fields = ("active",)
    ordering_fields = ("id", "code", "name", "domain", "created_at")
    default_ordering = "name"
    label_fields = ("name", "code")
    dependents = TENANT_DEPENDENTS

    async def prepare(self, data: dict, instance) -> dict:
        return self.apply_slug(dict(data), instance, "code", ("name", "domain"), "tenant")

    async def validate(self, db: AsyncSession, data: dict, instance) -> None:
        prepared = await self.prepare(data, instance)

        await self.ensure_unique(db, Tenant.code, prepared.get("code"), "error.code-already-used", "code", instance)
        await self.ensure_unique(db, Tenant.domain, prepared.get("domain"), "error.domain-already-used", "domain", instance)

    async def brand_of(self, db: AsyncSession, tenant_id: int | None) -> Brand:
        """The brand a row was written under, where a row of no tenant is the one this instance is."""
        return brand.of(await db.get(Tenant, tenant_id) if tenant_id is not None else None)


tenant_service = TenantService()
