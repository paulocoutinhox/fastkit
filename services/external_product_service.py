from sqlalchemy.ext.asyncio import AsyncSession

from models.external_product import ExternalProduct
from models.integration import Integration
from models.plan import Plan
from services.crud_service import CrudService
from services.reach import Reach


class ExternalProductService(CrudService):
    model = ExternalProduct
    shared = True
    reaches_through = Reach(ExternalProduct.integration_id, Integration)
    search_fields = ("external_id", "notes")
    text_search_fields = ("display_name",)
    filter_fields = ("integration_id", "plan_id", "active")
    ordering_fields = ("id", "external_id", "display_name", "created_at")
    default_ordering = "-id"
    relations = ("integration.tenant", "plan")
    label_fields = ("display_name", "external_id")

    async def validate(self, db: AsyncSession, data: dict, instance) -> None:
        """A gateway sells what its own brand reaches, and a plan of another would hand that brand's rights to a buyer of this one."""
        integration = await db.get(Integration, self.declared(data, instance, "integration_id"))

        await self.ensure_reaches(db, Plan, self.declared(data, instance, "plan_id"), integration.tenant_id, "plan_id")

    async def prepare(self, data: dict, instance) -> dict:
        prepared = dict(data)

        if prepared.get("reference_currency"):
            prepared["reference_currency"] = prepared["reference_currency"].upper()

        return prepared


external_product_service = ExternalProductService()
