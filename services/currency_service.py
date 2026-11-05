from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from helpers.scope import belongs_to_tenant, reaches_tenant
from models.currency import Currency
from models.entitlement import Entitlement
from services.crud_service import CrudService
from services.elsewhere import Elsewhere


class CurrencyService(CrudService):
    model = Currency
    shared = True
    search_fields = ("code",)
    text_search_fields = ("name",)
    filter_fields = ("tenant_id", "entitlement_id", "active")
    # A credit benefit pays in a currency its entitlement's brand reaches, which is the same cut the product of a benefit is offered by.
    filters_elsewhere = {"entitlement_id": Elsewhere(Entitlement.id, lambda value: and_(select(Entitlement.id).where(Entitlement.id == value).exists(), reaches_tenant(Currency.tenant_id, select(Entitlement.tenant_id).where(Entitlement.id == value).scalar_subquery())))}
    ordering_fields = ("id", "code", "name", "position", "created_at")
    default_ordering = "position"
    relations = ("tenant",)
    label_fields = ("name",)
    position_field = "position"

    async def prepare(self, data: dict, instance) -> dict:
        return self.apply_slug(dict(data), instance, "code", ("name",), "currency")

    async def validate(self, db: AsyncSession, data: dict, instance) -> None:
        prepared = await self.prepare(data, instance)
        tenant_id = self.declared(prepared, instance, "tenant_id")

        await self.ensure_unique(db, Currency.code, self.declared(prepared, instance, "code"), "error.code-already-used", "code", instance, belongs_to_tenant(Currency.tenant_id, tenant_id))


currency_service = CurrencyService()
