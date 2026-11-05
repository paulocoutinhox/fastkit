from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models.subscription import Subscription
from models.user_entitlement import UserEntitlement
from services.crud_service import CrudService
from services.elsewhere import Elsewhere
from services.reach import Reach


class UserEntitlementService(CrudService):
    model = UserEntitlement
    reaches_through = Reach(UserEntitlement.subscription_id, Subscription)
    search_fields = ()
    filter_fields = ("user_id", "entitlement_id", "status")
    filters_elsewhere = {"user_id": Elsewhere(Subscription.user_id, lambda value: UserEntitlement.subscription_id.in_(select(Subscription.id).where(Subscription.user_id == value)))}
    ordering_fields = ("id", "status", "expires_at", "created_at")
    default_ordering = "-id"
    relations = ("entitlement", "subscription.user")
    label_fields = ("id",)

    async def list_for_user(self, db: AsyncSession, user_id: int) -> list[UserEntitlement]:
        """What one account holds, read through the subscriptions that granted it."""
        owned = select(Subscription.id).where(Subscription.user_id == user_id)
        statement = select(UserEntitlement).options(selectinload(UserEntitlement.entitlement)).where(UserEntitlement.subscription_id.in_(owned)).order_by(UserEntitlement.id.desc())

        return list((await db.execute(statement)).scalars())


user_entitlement_service = UserEntitlementService()
