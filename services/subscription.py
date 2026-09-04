from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from enums.subscription import BenefitCadence, BenefitPolicy, BenefitType, SubscriptionStatus
from enums.upload import UploadPurpose
from helpers.errors import ValidationError
from models.commerce import Product
from models.integration import Integration, WebhookEvent
from models.subscription import Benefit, BenefitGrant, Entitlement, Plan, PlanEntitlement, Subscription, SubscriptionBenefit, UserEntitlement
from services.crud import CrudService, Dependent, Elsewhere, LocalizedService, Reach


def benefit_policy_of(subscription: Subscription, plan: Plan) -> BenefitPolicy:
    """What a subscription hands over in the state it is in, which trial and grace narrow and nothing else does."""
    if subscription.status == SubscriptionStatus.TRIALING:
        return plan.trial_benefit_policy

    if subscription.status == SubscriptionStatus.GRACE_PERIOD:
        return plan.grace_benefit_policy

    return BenefitPolicy.ALL


class EntitlementService(CrudService):
    model = Entitlement
    markup_fields = ("description",)
    search_fields = ()
    text_search_fields = ("name",)
    filter_fields = ("tenant_id", "active")
    ordering_fields = ("id", "name", "created_at")
    default_ordering = "name"
    relations = ("tenant",)
    label_fields = ("name",)
    dependents = (Dependent(Benefit, "entitlement_id"), Dependent(PlanEntitlement, "entitlement_id"))


class PlanService(LocalizedService):
    model = Plan
    localized_key = "code"
    search_fields = ("code",)
    text_search_fields = ("name",)
    filter_fields = ("tenant_id", "language_id", "integration_id", "featured", "active")

    # A gateway sells what its own tenant offers, so pointing one at a plan of another tenant is not a choice the form gives.
    filters_elsewhere = {"integration_id": Elsewhere(Integration.id, lambda value: Plan.tenant_id.in_(select(Integration.tenant_id).where(Integration.id == value)))}

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
        offered = self.by_language(self.base_statement().where(Plan.tenant_id == tenant_id, Plan.active.is_(True)), language)

        return self.one_per_key((await db.execute(offered)).scalars().unique(), ("position", "id"))

    async def validate(self, db: AsyncSession, data: dict, instance) -> None:
        prepared = await self.prepare(data, instance)
        tenant_id = self.declared(prepared, instance, "tenant_id")

        self.validate_billing_interval(self.declared(prepared, instance, "billing_interval_unit"), self.declared(prepared, instance, "billing_interval_value"))

        code = prepared.get("code")

        if not code:
            return

        language_id = self.declared(prepared, instance, "language_id")
        same_language = Plan.language_id.is_(None) if language_id is None else Plan.language_id == language_id
        statement = select(Plan.id).where(Plan.tenant_id == tenant_id, Plan.code == code, same_language)

        if instance is not None:
            statement = statement.where(Plan.id != instance.id)

        if await db.scalar(statement) is not None:
            raise ValidationError("error.code-already-used", "code")


class PlanEntitlementService(CrudService):
    model = PlanEntitlement
    reaches_through = Reach(PlanEntitlement.plan_id, Plan)
    search_fields = ()
    filter_fields = ("plan_id", "entitlement_id")
    ordering_fields = ("id", "created_at")
    default_ordering = "-id"
    relations = ("plan", "entitlement")
    label_fields = ("id",)


class BenefitService(CrudService):
    model = Benefit
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
        await self.ensure_product_reaches(db, self.declared(prepared, instance, "entitlement_id"), product_id)

    async def ensure_product_reaches(self, db: AsyncSession, entitlement_id: int, product_id: int | None) -> None:
        """The form narrows the list and this is what refuses what somebody sent anyway, which is the half that counts."""
        if product_id is None:
            return

        entitlement = await db.get(Entitlement, entitlement_id)
        product = await db.get(Product, product_id)

        if product is None or (product.tenant_id is not None and product.tenant_id != entitlement.tenant_id):
            raise ValidationError("error.product-out-of-tenant", "product_id")

    def validate_interval(self, cadence, interval_unit, interval_value) -> None:
        if cadence == BenefitCadence.RECURRING:
            if not interval_unit or not interval_value:
                raise ValidationError("error.benefit-recurring-requires-interval", "interval_unit")

            if interval_value < 1:
                raise ValidationError("error.benefit-interval-value-min", "interval_value")

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


class SubscriptionBenefitService(CrudService):
    model = SubscriptionBenefit
    reaches_through = Reach(SubscriptionBenefit.subscription_id, Subscription)
    search_fields = ("target",)
    filter_fields = ("user_id", "benefit_id", "status", "benefit_type")
    filters_elsewhere = {"user_id": Elsewhere(Subscription.user_id, lambda value: SubscriptionBenefit.subscription_id.in_(select(Subscription.id).where(Subscription.user_id == value)))}
    ordering_fields = ("id", "next_grant_at", "last_grant_at", "created_at")
    default_ordering = "-id"
    relations = ("subscription.user", "product", "currency")
    label_fields = ("target",)
    dependents = (Dependent(BenefitGrant, "subscription_benefit_id"),)


class BenefitGrantService(CrudService):
    model = BenefitGrant
    reaches_through = Reach(BenefitGrant.subscription_benefit_id, SubscriptionBenefit, Reach(SubscriptionBenefit.subscription_id, Subscription))
    search_fields = ("grant_key", "cycle_key")
    filter_fields = ("user_id", "status")
    filters_elsewhere = {"user_id": Elsewhere(Subscription.user_id, lambda value: BenefitGrant.subscription_benefit_id.in_(select(SubscriptionBenefit.id).where(SubscriptionBenefit.subscription_id.in_(select(Subscription.id).where(Subscription.user_id == value)))))}
    ordering_fields = ("id", "scheduled_at", "status", "created_at")
    default_ordering = "-id"
    relations = ("subscription_benefit.subscription.user",)
    label_fields = ("grant_key",)


entitlement_service = EntitlementService()
plan_service = PlanService()
plan_entitlement_service = PlanEntitlementService()
benefit_service = BenefitService()
subscription_service = SubscriptionService()
user_entitlement_service = UserEntitlementService()
subscription_benefit_service = SubscriptionBenefitService()
benefit_grant_service = BenefitGrantService()
