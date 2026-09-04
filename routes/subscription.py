from fastapi import APIRouter

from helpers import audit, cache, idempotency
from helpers.auth import AdministratorUser, CurrentBrand, CurrentUser
from helpers.crud import RecordId, build_readonly_router, build_router
from helpers.db import DatabaseSession
from helpers.errors import NotFoundError
from helpers.i18n import current_locale
from helpers.idempotency import IdempotencyKey
from helpers.pagination import ListingLimit, ListingOffset, Page
from schemas.common import BaseSchema, ReturnUrl
from schemas.subscription import (
    AccountSubscriptionListResponse,
    BenefitCreate,
    BenefitGrantSchema,
    BenefitSchema,
    BenefitUpdate,
    CatalogPlanSchema,
    EntitlementCreate,
    EntitlementSchema,
    EntitlementUpdate,
    PlanCreate,
    PlanEntitlementCreate,
    PlanEntitlementSchema,
    PlanEntitlementUpdate,
    PlanSchema,
    PlanUpdate,
    SubscriptionBenefitSchema,
    SubscriptionSchema,
    SubscriptionTransactionSchema,
    UserEntitlementSchema,
    catalogued,
)
from services.checkout import checkout_service
from services.delivery import delivery_service
from services.subscription import benefit_grant_service, benefit_service, entitlement_service, plan_entitlement_service, plan_service, subscription_benefit_service, subscription_service, user_entitlement_service

public_router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])
account_router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])
activation_router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])


class ActivationResponse(BaseSchema):
    granted: int


class CatalogPlanListResponse(BaseSchema):
    items: list[CatalogPlanSchema]


class PlanCheckoutRequest(BaseSchema):
    """Where the gateway sends the buyer back to, which an application names because only it knows its own way home."""

    success_url: ReturnUrl
    cancel_url: ReturnUrl


class PlanCheckoutResponse(BaseSchema):
    url: str


@public_router.get("/plans", response_model=CatalogPlanListResponse, summary="List the plans a tenant sells")
async def list_plans(db: DatabaseSession, brand: CurrentBrand):
    """What an application puts on its own paywall, which is the same list the site draws."""
    language = current_locale.get()

    async def build():
        return [catalogued(plan).model_dump(mode="json") for plan in await plan_service.list_offered(db, brand.id, language)]

    entries = await cache.answered(cache.plans, cache.named(surface="api", tenant=brand.id, language=language), build)

    return CatalogPlanListResponse(items=[CatalogPlanSchema(**entry) for entry in entries])


@public_router.post("/plans/{code}/checkout", response_model=PlanCheckoutResponse, summary="Open a payment for one plan")
async def subscribe_to_plan(db: DatabaseSession, brand: CurrentBrand, user: CurrentUser, code: str, payload: PlanCheckoutRequest, idempotency_key: IdempotencyKey = None):
    """A store sells a subscription inside the application, and this is the same door the site sends a buyer through."""
    plan = next((offer for offer in await plan_service.list_offered(db, brand.id, current_locale.get()) if offer.code == code), None)

    if plan is None:
        raise NotFoundError()

    named, kept = await idempotency.claim(db, user, idempotency_key, "subscription-plan-checkout")

    if kept is not None:
        return PlanCheckoutResponse(**kept)

    answer = PlanCheckoutResponse(url=await checkout_service.for_plan(db, brand, user, plan, payload.success_url, payload.cancel_url))
    await idempotency.settle(db, named, answer.model_dump())

    return answer


@account_router.get("/me", response_model=AccountSubscriptionListResponse, summary="List the subscriptions of the signed in account")
async def list_me(db: DatabaseSession, user: CurrentUser):
    items = await subscription_service.list_for_user(db, user.id)

    return AccountSubscriptionListResponse(items=[SubscriptionSchema.model_validate(item) for item in items])


@account_router.get("/{subscription_id}/transactions", response_model=Page[SubscriptionTransactionSchema], summary="List what the provider reported about a subscription")
async def list_transactions(db: DatabaseSession, user: CurrentUser, subscription_id: RecordId, limit: ListingLimit = 50, offset: ListingOffset = 0):
    """A subscription of somebody else is one that does not exist here, or an empty answer would read as one with no payments yet."""
    if await subscription_service.find_for_user(db, user.id, subscription_id) is None:
        raise NotFoundError()

    total, items = await subscription_service.list_transactions(db, user.id, subscription_id, limit, offset)

    return Page[SubscriptionTransactionSchema](count=total, limit=limit, offset=offset, items=[SubscriptionTransactionSchema.model_validate(item) for item in items])


@activation_router.post("/{record_id}/activate", response_model=ActivationResponse, summary="Reconcile and deliver what a subscription owes")
async def activate(db: DatabaseSession, administrator: AdministratorUser, record_id: RecordId):
    """The engine runs this on its own, so an operator running it by hand is what has to be written down."""
    subscription = await subscription_service.get(db, record_id)
    grants = await delivery_service.activate(db, subscription)
    await audit.written(db, administrator, "activated", "subscriptions", record_id)

    return ActivationResponse(granted=len(grants))


@activation_router.post("/{record_id}/new-cycle", response_model=ActivationResponse, summary="Open a fresh cycle and deliver it")
async def open_new_cycle(db: DatabaseSession, administrator: AdministratorUser, record_id: RecordId):
    """Coming back is the same cycle by default, and this is the one door out of that: an operator says so, and it is written down."""
    subscription = await subscription_service.get(db, record_id)
    grants = await delivery_service.open_new_cycle(db, subscription, administrator)

    return ActivationResponse(granted=len(grants))


router = build_readonly_router(subscription_service, SubscriptionSchema, "/subscriptions", "subscriptions")
plan_router = build_router(plan_service, PlanSchema, PlanCreate, PlanUpdate, "/plans", "plans")
entitlement_router = build_router(entitlement_service, EntitlementSchema, EntitlementCreate, EntitlementUpdate, "/entitlements", "entitlements")
plan_entitlement_router = build_router(plan_entitlement_service, PlanEntitlementSchema, PlanEntitlementCreate, PlanEntitlementUpdate, "/plan-entitlements", "plan entitlements")
benefit_router = build_router(benefit_service, BenefitSchema, BenefitCreate, BenefitUpdate, "/benefits", "benefits")
user_entitlement_router = build_readonly_router(user_entitlement_service, UserEntitlementSchema, "/user-entitlements", "user entitlements")
subscription_benefit_router = build_readonly_router(subscription_benefit_service, SubscriptionBenefitSchema, "/subscription-benefits", "subscription benefits")
benefit_grant_router = build_readonly_router(benefit_grant_service, BenefitGrantSchema, "/benefit-grants", "benefit grants")
