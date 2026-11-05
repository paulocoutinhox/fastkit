from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models.benefit_grant import BenefitGrant
from models.subscription import Subscription
from models.subscription_benefit import SubscriptionBenefit
from models.user_entitlement import UserEntitlement
from models.webhook_event import WebhookEvent
from services.crud_service import CrudService
from services.dependent import Dependent


class SubscriptionService(CrudService):
    model = Subscription
    search_fields = ("external_id",)
    filter_fields = ("tenant_id", "user_id", "plan_id", "integration_id", "status", "benefit_status")
    ordering_fields = ("id", "status", "started_at", "current_period_ends_at", "created_at")
    default_ordering = "-id"
    relations = ("tenant", "user", "plan")
    label_fields = ("id",)
    dependents = (Dependent(SubscriptionBenefit, "subscription_id", dependents=(Dependent(BenefitGrant, "subscription_benefit_id"),)), Dependent(UserEntitlement, "subscription_id"))

    async def list_for_user(self, db: AsyncSession, user_id: int) -> list[Subscription]:
        """The account reads its own plan and nothing else, so the tenant and the user the admin needs are not loaded here."""
        statement = select(Subscription).options(selectinload(Subscription.plan)).where(Subscription.user_id == user_id).order_by(Subscription.id.desc())

        return list((await db.execute(statement)).scalars().unique())

    async def find_for_user(self, db: AsyncSession, user_id: int, subscription_id: int) -> Subscription | None:
        """The subscription of this account and no other, because the number in the path is what somebody typed."""
        return await db.scalar(select(Subscription).options(selectinload(Subscription.plan)).where(Subscription.id == subscription_id, Subscription.user_id == user_id))

    async def list_transactions(self, db: AsyncSession, user_id: int, subscription_id: int, limit: int, offset: int) -> tuple[int, list[WebhookEvent]]:
        owned = select(Subscription.id).where(Subscription.id == subscription_id, Subscription.user_id == user_id)
        held = WebhookEvent.subscription_id.in_(owned)

        total = await db.scalar(select(func.count()).select_from(WebhookEvent).where(held))
        statement = select(WebhookEvent).where(held).order_by(WebhookEvent.occurred_at.is_(None), WebhookEvent.occurred_at.desc(), WebhookEvent.id.desc()).limit(limit).offset(offset)

        return total, list((await db.execute(statement)).scalars())


subscription_service = SubscriptionService()
