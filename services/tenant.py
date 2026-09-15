from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from enums.user import PANEL_ROLES
from models.account import CreditTransaction, Currency, UserBalance
from models.banner import Banner
from models.commerce import Product, Purchase, UserProduct
from models.content import Content
from models.event import AppEvent
from models.gallery import Gallery, GalleryPhoto
from models.integration import ExternalProduct, Integration, WebhookEvent
from models.subscription import Benefit, BenefitGrant, Entitlement, Plan, PlanEntitlement, Subscription, SubscriptionBenefit, UserEntitlement
from models.system_log import SystemLog
from models.tenant import Tenant
from models.user import User, UserAddress
from services.crud import CrudService, Dependent

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

    async def code_of(self, db: AsyncSession, tenant_id: int | None) -> str | None:
        """The storage and the mailer are keyed by the code, and an account without a tenant answers none."""
        if tenant_id is None:
            return None

        return await db.scalar(select(Tenant.code).where(Tenant.id == tenant_id))


tenant_service = TenantService()
