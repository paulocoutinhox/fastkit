from sqlalchemy.ext.asyncio import AsyncSession

from enums.benefit_cadence import BenefitCadence
from enums.benefit_type import BenefitType
from enums.interval_unit import IntervalUnit
from helpers.dates import add_interval, now
from helpers.validation_error import ValidationError
from models.benefit import Benefit
from models.currency import Currency
from models.entitlement import Entitlement
from models.product import Product
from services.crud_service import CrudService
from services.reach import Reach

# A benefit that repeats less often than this is one nobody is going to see twice, and the calendar ends a few thousand years out.
INTERVAL_CEILING_YEARS = 100


class BenefitService(CrudService):
    model = Benefit
    shared = True
    reaches_through = Reach(Benefit.entitlement_id, Entitlement)
    search_fields = ("target",)
    filter_fields = ("entitlement_id", "product_id", "currency_id", "type", "cadence", "active")
    ordering_fields = ("id", "type", "created_at")
    default_ordering = "-id"
    relations = ("entitlement", "product", "currency")
    label_fields = ("target",)

    async def validate(self, db: AsyncSession, data: dict, instance) -> None:
        prepared = dict(data)

        cadence = self.declared(prepared, instance, "cadence")
        interval_unit = self.declared(prepared, instance, "interval_unit")
        interval_value = self.declared(prepared, instance, "interval_value")

        self.validate_interval(cadence, interval_unit, interval_value)

        benefit_type = self.declared(prepared, instance, "type")
        quantity = self.declared(prepared, instance, "quantity")
        product_id = self.declared(prepared, instance, "product_id")
        currency_id = self.declared(prepared, instance, "currency_id")

        self.validate_payload(benefit_type, quantity, product_id, currency_id)

        entitlement = await db.get(Entitlement, self.declared(prepared, instance, "entitlement_id"))

        await self.ensure_reaches(db, Product, product_id, entitlement.tenant_id, "product_id", "error.product-out-of-tenant")
        await self.ensure_reaches(db, Currency, currency_id, entitlement.tenant_id, "currency_id")

    def validate_interval(self, cadence, interval_unit, interval_value) -> None:
        if cadence == BenefitCadence.RECURRING:
            if not interval_unit or not interval_value:
                raise ValidationError("error.benefit-recurring-requires-interval", "interval_unit")

            if interval_value < 1:
                raise ValidationError("error.benefit-interval-value-min", "interval_value")

            # Every activation walks the schedule by this step, so one the calendar cannot hold would refuse the plan on every notice for good.
            moment = now()

            try:
                step = add_interval(moment, interval_unit, interval_value)
            except (OverflowError, ValueError) as error:
                raise ValidationError("error.benefit-interval-too-long", "interval_value", years=INTERVAL_CEILING_YEARS) from error

            if step > add_interval(moment, IntervalUnit.YEAR, INTERVAL_CEILING_YEARS):
                raise ValidationError("error.benefit-interval-too-long", "interval_value", years=INTERVAL_CEILING_YEARS)

            return

        if interval_unit or interval_value:
            raise ValidationError("error.benefit-non-recurring-no-interval", "interval_unit")

    def validate_payload(self, benefit_type, quantity, product_id, currency_id) -> None:
        if benefit_type in (BenefitType.CREDIT, BenefitType.PRODUCT) and (quantity is None or quantity <= 0):
            raise ValidationError("error.benefit-quantity-must-be-positive", "quantity")

        if benefit_type == BenefitType.CREDIT and currency_id is None:
            raise ValidationError("error.benefit-credit-requires-currency", "currency_id")

        if benefit_type != BenefitType.CREDIT and currency_id is not None:
            raise ValidationError("error.benefit-currency-only-on-a-credit-benefit", "currency_id")

        if benefit_type == BenefitType.PRODUCT and product_id is None:
            raise ValidationError("error.benefit-product-requires-product", "product_id")

        if benefit_type != BenefitType.PRODUCT and product_id is not None:
            raise ValidationError("error.benefit-product-only-on-a-product-benefit", "product_id")


benefit_service = BenefitService()
