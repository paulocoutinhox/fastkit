from sqlalchemy.ext.asyncio import AsyncSession

from models.entitlement import Entitlement
from models.plan import Plan
from models.plan_entitlement import PlanEntitlement
from services.crud_service import CrudService
from services.reach import Reach


class PlanEntitlementService(CrudService):
    model = PlanEntitlement
    shared = True
    reaches_through = Reach(PlanEntitlement.plan_id, Plan)
    search_fields = ()
    filter_fields = ("plan_id", "entitlement_id")
    ordering_fields = ("id", "created_at")
    default_ordering = "-id"
    relations = ("plan", "entitlement")
    label_fields = ("id",)

    async def validate(self, db: AsyncSession, data: dict, instance) -> None:
        """A plan grants what its own brand reaches, and a shared plan grants only what every brand shares."""
        plan = await db.get(Plan, self.declared(data, instance, "plan_id"))

        await self.ensure_reaches(db, Entitlement, self.declared(data, instance, "entitlement_id"), plan.tenant_id, "entitlement_id")


plan_entitlement_service = PlanEntitlementService()
