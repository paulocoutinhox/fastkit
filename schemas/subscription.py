from datetime import datetime
from decimal import Decimal

from pydantic import Field

from enums.integration import Environment, NormalizedAction, WebhookEventStatus
from enums.subscription import BenefitCadence, BenefitGrantStatus, BenefitPolicy, BenefitStatus, BenefitType, IntervalUnit, MissedCyclePolicy, ResumeDeliveryPolicy, SubscriptionStatus, UserEntitlementStatus
from helpers.storage import storage
from schemas.account import CurrencyReference
from schemas.commerce import ProductReference
from schemas.common import FREE_TEXT_MAX, BaseSchema, IntervalValue, OptionalReference, Position, Quantity, Reference, Text, TimestampSchema, as_optional
from schemas.language import LanguageReference
from schemas.tenant import TenantReference
from schemas.user import UserReference


class EntitlementReference(BaseSchema):
    id: int
    name: str


class EntitlementSchema(TimestampSchema):
    id: int
    tenant_id: int | None
    tenant: TenantReference | None
    code: str
    name: str
    description: str | None
    active: bool
    meta: dict


class EntitlementCreate(BaseSchema):
    tenant_id: OptionalReference
    code: Text(64)
    name: Text(255)
    description: str | None = Field(None, max_length=FREE_TEXT_MAX)
    active: bool = True
    meta: dict = Field(default_factory=dict)


EntitlementUpdate = as_optional("EntitlementUpdate", EntitlementCreate)


class PlanReference(BaseSchema):
    id: int
    uuid: str
    code: str
    name: str
    currency: str
    price: Decimal


class PlanSchema(TimestampSchema):
    id: int
    uuid: str
    tenant_id: int | None
    tenant: TenantReference | None
    language_id: int | None
    language: LanguageReference | None
    code: str
    name: str
    description: str | None
    image: str | None
    currency: str
    price: Decimal
    billing_interval_unit: IntervalUnit | None
    billing_interval_value: int | None
    resume_delivery_policy: ResumeDeliveryPolicy
    trial_benefit_policy: BenefitPolicy
    grace_benefit_policy: BenefitPolicy
    featured: bool
    position: int
    active: bool
    meta: dict


class CatalogPlanSchema(BaseSchema):
    """What a client is offered, where the image is an address and never the key the admin edits."""

    id: int
    uuid: str
    code: str
    name: str
    description: str | None
    image_url: str | None
    currency: str
    price: Decimal
    billing_interval_unit: IntervalUnit | None
    billing_interval_value: int | None
    featured: bool


def catalogued(plan) -> CatalogPlanSchema:
    """A plan is the one thing the site and an application are answered the same, so it is assembled once instead of once per surface."""
    return CatalogPlanSchema(
        id=plan.id,
        uuid=plan.uuid,
        code=plan.code,
        name=plan.name,
        description=plan.description,
        image_url=storage.url(plan.image) if plan.image else None,
        currency=plan.currency,
        price=plan.price,
        billing_interval_unit=plan.billing_interval_unit,
        billing_interval_value=plan.billing_interval_value,
        featured=plan.featured,
    )


class PlanCreate(BaseSchema):
    tenant_id: OptionalReference
    language_id: OptionalReference
    code: str | None = Field(None, max_length=64)
    name: Text(255)
    description: str | None = Field(None, max_length=FREE_TEXT_MAX)
    image: str | None = Field(None, max_length=512)
    currency: str = Field("USD", min_length=3, max_length=3)
    price: Decimal = Field(Decimal("0"), ge=0)
    billing_interval_unit: IntervalUnit | None = None
    billing_interval_value: IntervalValue
    resume_delivery_policy: ResumeDeliveryPolicy = ResumeDeliveryPolicy.SAME_CYCLE
    trial_benefit_policy: BenefitPolicy = BenefitPolicy.ACCESS_ONLY
    grace_benefit_policy: BenefitPolicy = BenefitPolicy.ACCESS_ONLY
    featured: bool = False
    position: Position
    active: bool = True
    meta: dict = Field(default_factory=dict)


PlanUpdate = as_optional("PlanUpdate", PlanCreate)


class PlanEntitlementSchema(TimestampSchema):
    id: int
    plan_id: int
    plan: PlanReference | None
    entitlement_id: int
    entitlement: EntitlementReference | None
    meta: dict


class PlanEntitlementCreate(BaseSchema):
    plan_id: Reference
    entitlement_id: Reference
    meta: dict = Field(default_factory=dict)


PlanEntitlementUpdate = as_optional("PlanEntitlementUpdate", PlanEntitlementCreate)


class BenefitSchema(TimestampSchema):
    id: int
    entitlement_id: int
    entitlement: EntitlementReference | None
    product_id: int | None
    product: ProductReference | None
    currency_id: int | None
    currency: CurrencyReference | None
    type: BenefitType
    target: str
    quantity: int
    cadence: BenefitCadence
    interval_unit: IntervalUnit | None
    interval_value: int | None
    grant_on_activation: bool
    missed_cycle_policy: MissedCyclePolicy
    active: bool
    meta: dict


class BenefitCreate(BaseSchema):
    entitlement_id: Reference
    product_id: OptionalReference
    currency_id: OptionalReference
    type: BenefitType
    target: Text(191)
    quantity: Quantity
    cadence: BenefitCadence
    interval_unit: IntervalUnit | None = None
    interval_value: IntervalValue
    grant_on_activation: bool = True
    missed_cycle_policy: MissedCyclePolicy = MissedCyclePolicy.SKIP
    active: bool = True
    meta: dict = Field(default_factory=dict)


BenefitUpdate = as_optional("BenefitUpdate", BenefitCreate)


class SubscriptionSchema(TimestampSchema):
    id: int
    tenant_id: int | None
    tenant: TenantReference | None
    user_id: int
    user: UserReference | None
    plan_id: int
    plan: PlanReference | None
    integration_id: int | None
    external_product_id: int | None
    external_id: str | None
    status: SubscriptionStatus
    benefit_status: BenefitStatus
    environment: Environment | None
    started_at: datetime | None
    current_period_started_at: datetime | None
    current_period_ends_at: datetime | None
    access_until: datetime | None
    trial_ends_at: datetime | None
    grace_until: datetime | None
    cancel_at_period_end: bool
    canceled_at: datetime | None
    expired_at: datetime | None
    meta: dict


class SubscriptionReference(BaseSchema):
    id: int
    user: UserReference | None


class AccountSubscriptionSchema(TimestampSchema):
    """What an account reads about what it pays for, without the ids the admin needs."""

    id: int
    plan: PlanReference
    status: SubscriptionStatus
    benefit_status: BenefitStatus
    started_at: datetime | None
    current_period_started_at: datetime | None
    current_period_ends_at: datetime | None
    access_until: datetime | None
    trial_ends_at: datetime | None
    grace_until: datetime | None
    cancel_at_period_end: bool
    canceled_at: datetime | None
    expired_at: datetime | None


class AccountSubscriptionListResponse(BaseSchema):
    items: list[AccountSubscriptionSchema]


class UserEntitlementSchema(TimestampSchema):
    id: int
    subscription_id: int
    subscription: SubscriptionReference | None
    entitlement_id: int
    entitlement: EntitlementReference | None
    status: UserEntitlementStatus
    started_at: datetime | None
    expires_at: datetime | None
    revoked_at: datetime | None
    meta: dict


class SubscriptionBenefitSchema(TimestampSchema):
    id: int
    subscription_id: int
    subscription: SubscriptionReference | None
    benefit_id: int
    user_entitlement_id: int
    product_id: int | None
    product: ProductReference | None
    currency_id: int | None
    currency: CurrencyReference | None
    status: BenefitStatus
    benefit_type: BenefitType
    target: str
    quantity: int
    cadence: BenefitCadence
    interval_unit: IntervalUnit | None
    interval_value: int | None
    grant_on_activation: bool
    missed_cycle_policy: MissedCyclePolicy
    anchor_at: datetime
    last_grant_at: datetime | None
    next_grant_at: datetime | None
    meta: dict


class BenefitGrantSchema(TimestampSchema):
    id: int
    subscription_benefit_id: int
    grant_key: str
    cycle_key: str
    scheduled_at: datetime
    status: BenefitGrantStatus
    requested_quantity: int
    granted_quantity: int
    result: dict
    error_code: str | None
    error_message: str | None
    attempts: int
    started_at: datetime | None
    completed_at: datetime | None
    meta: dict


class SubscriptionTransactionSchema(BaseSchema):
    """What the provider reported: the amount is in the currency the buyer paid, which the store decides and not the plan."""

    id: int
    action: NormalizedAction | None
    status: WebhookEventStatus
    amount: Decimal | None
    currency: str | None
    occurred_at: datetime | None
    created_at: datetime


class AccountEntitlementSchema(BaseSchema):
    """What the signed in account holds, keyed by the code an app gates a feature with."""

    code: str
    name: str
    status: UserEntitlementStatus
    started_at: datetime | None
    expires_at: datetime | None
