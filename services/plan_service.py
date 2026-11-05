from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from enums.upload_purpose import UploadPurpose
from helpers.scope import belongs_to_tenant, reaches_tenant
from helpers.validation_error import ValidationError
from models.integration import Integration
from models.plan import Plan
from models.plan_entitlement import PlanEntitlement
from services.dependent import Dependent
from services.elsewhere import Elsewhere
from services.localized_service import LocalizedService


class PlanService(LocalizedService):
    model = Plan
    shared = True
    localized_key = "code"
    search_fields = ("code",)
    text_search_fields = ("name",)
    filter_fields = ("tenant_id", "language_id", "integration_id", "featured", "active")

    # A gateway sells what its own tenant reaches, its own plans and the shared ones, so a plan of another tenant is not a choice the form gives.
    # An IN over the tenant of the integration matched nothing where that tenant is null, which is every integration of a single brand.
    filters_elsewhere = {"integration_id": Elsewhere(Integration.id, lambda value: and_(select(Integration.id).where(Integration.id == value).exists(), reaches_tenant(Plan.tenant_id, select(Integration.tenant_id).where(Integration.id == value).scalar_subquery())))}

    ordering_fields = ("id", "code", "name", "price", "position", "created_at")
    default_ordering = "position"
    relations = ("tenant", "language")
    label_fields = ("name",)
    file_fields = {"image": UploadPurpose.PLAN_IMAGE}
    markup_fields = ("description",)
    dependents = (Dependent(PlanEntitlement, "plan_id"),)

    async def prepare(self, data: dict, instance) -> dict:
        return self.apply_slug(dict(data), instance, "code", ("name",), "plan")

    def validate_billing_interval(self, unit, value) -> None:
        """How often a plan bills is a unit and a number together, and the page draws the sentence off the unit alone."""
        if bool(unit) == bool(value):
            return

        raise ValidationError("error.plan-billing-interval-incomplete", "billing_interval_value" if unit else "billing_interval_unit")

    async def list_offered(self, db: AsyncSession, tenant_id: int, language: str | None = None) -> list[Plan]:
        """What a tenant sells right now, one row per code and in the language of whoever is reading it, because a price is written in the currency of a market."""
        # A shared plan is sold by every brand that has none of its own under that code, which is the tie the ranking of the language breaks.
        offered = self.by_language(self.base_statement().where(reaches_tenant(Plan.tenant_id, tenant_id), Plan.active.is_(True)), language)

        return self.one_per_key((await db.execute(offered)).scalars().unique(), ("position", "id"))

    async def validate(self, db: AsyncSession, data: dict, instance) -> None:
        prepared = await self.prepare(data, instance)
        tenant_id = self.declared(prepared, instance, "tenant_id")

        self.validate_billing_interval(self.declared(prepared, instance, "billing_interval_unit"), self.declared(prepared, instance, "billing_interval_value"))

        # The code is read off the row too, because moving a plan to another brand alone is enough to land it on a code that brand already sells.
        code = self.declared(prepared, instance, "code")
        language_id = self.declared(prepared, instance, "language_id")
        same_language = Plan.language_id.is_(None) if language_id is None else Plan.language_id == language_id

        await self.ensure_unique(db, Plan.code, code, "error.code-already-used", "code", instance, and_(belongs_to_tenant(Plan.tenant_id, tenant_id), same_language))


plan_service = PlanService()
