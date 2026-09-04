import asyncio
import logging
from enum import StrEnum

from fastapi import APIRouter, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from starlette.responses import JSONResponse

from enums.account import CreditTransactionType
from enums.banner import BannerPlacement
from enums.captcha import CaptchaProvider
from enums.commerce import PurchaseStatus
from enums.country import PostalCodeProvider
from enums.email import OutboundEmailStatus
from enums.event import AppEventStatus
from enums.integration import Environment, NormalizedAction, Provider, WebhookEventStatus
from enums.newsletter import NewsletterStatus
from enums.subscription import BenefitCadence, BenefitGrantStatus, BenefitPolicy, BenefitStatus, BenefitType, IntervalUnit, MissedCyclePolicy, ResumeDeliveryPolicy, SubscriptionStatus, UserEntitlementStatus
from enums.system_log import LogCategory, LogLevel
from enums.user import UserAddressType, UserGender, UserRole, UserStatus
from helpers import captcha, visitor
from helpers.auth import CurrentUser
from helpers.crud import RESOURCES
from helpers.db import DatabaseSession
from helpers.settings import settings
from schemas.common import TIMEZONES, BaseSchema
from services.gateway import PROVIDERS

CATALOG: dict[str, type[StrEnum]] = {
    "app_event_status": AppEventStatus,
    "banner_placement": BannerPlacement,
    "benefit_cadence": BenefitCadence,
    "benefit_grant_status": BenefitGrantStatus,
    "benefit_policy": BenefitPolicy,
    "benefit_status": BenefitStatus,
    "benefit_type": BenefitType,
    "credit_transaction_type": CreditTransactionType,
    "environment": Environment,
    "interval_unit": IntervalUnit,
    "log_category": LogCategory,
    "log_level": LogLevel,
    "missed_cycle_policy": MissedCyclePolicy,
    "newsletter_status": NewsletterStatus,
    "normalized_action": NormalizedAction,
    "outbound_email_status": OutboundEmailStatus,
    "postal_code_provider": PostalCodeProvider,
    "provider": Provider,
    "purchase_status": PurchaseStatus,
    "resume_delivery_policy": ResumeDeliveryPolicy,
    "subscription_status": SubscriptionStatus,
    "user_address_type": UserAddressType,
    "user_entitlement_status": UserEntitlementStatus,
    "user_gender": UserGender,
    "user_role": UserRole,
    "user_status": UserStatus,
    "webhook_event_status": WebhookEventStatus,
}

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/meta", tags=["meta"])


class CredentialSchema(BaseSchema):
    field: str
    label: str
    hint: str


class CaptchaSchema(BaseSchema):
    """What a form has to draw, where the secret half never leaves the server."""

    provider: CaptchaProvider
    site_key: str


class ChallengeSchema(BaseSchema):
    """One challenge, minted for the form about to be sent, where the half that proves the answer stays signed inside the token."""

    provider: CaptchaProvider
    token: str
    image: str
    site_key: str


class VisitorSchema(BaseSchema):
    """A name signed by this side, which an application keeps and sends back when it counts a banner."""

    visitor: str


class PermissionsResponse(BaseSchema):
    """The resources this account reaches, which is what the panel draws a menu out of."""

    resources: list[str]

    # An account that belongs to a brand writes into that brand and no other, so the panel stops drawing a field with one option.
    confined: bool


class MetaResponse(BaseSchema):
    name: str
    environment: str
    version: str
    default_language: str
    languages: dict[str, str]
    storage_base_url: str
    enums: dict[str, list[str]]
    captcha: CaptchaSchema
    provider_credentials: dict[str, list[CredentialSchema]]
    timezones: list[str]


class HealthResponse(BaseSchema):
    status: str


@router.get("", response_model=MetaResponse, summary="Read what the admin needs to render its forms")
async def read_meta():
    return MetaResponse(
        name=settings.name,
        environment=settings.environment,
        version=settings.version,
        default_language=settings.default_language,
        languages=settings.languages,
        storage_base_url=settings.storage.base_url,
        enums={name: [member.value for member in enum_class] for name, enum_class in CATALOG.items()},
        captcha=CaptchaSchema(provider=settings.captcha.provider, site_key=settings.captcha.site_key),
        provider_credentials={provider.value: [CredentialSchema(field=credential.field, label=credential.label, hint=credential.hint) for credential in gateway.credentials] for provider, gateway in PROVIDERS.items()},
        timezones=TIMEZONES,
    )


@router.get("/captcha", response_model=ChallengeSchema, summary="Draw a captcha challenge")
async def read_captcha():
    challenge = captcha.issue()

    return ChallengeSchema(provider=challenge.kind, token=challenge.token, image=challenge.image, site_key=challenge.site_key)


@router.get("/visitor", response_model=VisitorSchema, summary="A name a reader may be counted by")
async def read_visitor():
    """An application asks for one where its reader allowed analytics, exactly as the site writes one into a cookie there."""
    return VisitorSchema(visitor=visitor.minted())


@router.get("/permissions", response_model=PermissionsResponse, summary="What the signed in account reaches")
async def read_permissions(user: CurrentUser):
    """What this account reaches and never the whole map, because the shape of who reaches what is not a catalogue."""
    reachable = sorted(name for name, service in RESOURCES.items() if user.role in service.roles and not (service.system_wide and user.tenant_id is not None))

    return PermissionsResponse(resources=reachable, confined=user.tenant_id is not None)


@router.get("/health", response_model=HealthResponse, summary="Liveness probe")
async def health():
    """Whether this process is answering, which is what says restart it — and never whether it can serve, because restarting fixes no database."""
    return HealthResponse(status="ok")


@router.get("/ready", response_model=HealthResponse, summary="Readiness probe")
async def ready(db: DatabaseSession):
    """Whether this copy can serve, which is what a balancer reads to stop sending it traffic while it cannot."""
    try:
        async with asyncio.timeout(settings.readiness_timeout):
            await db.execute(text("SELECT 1"))
    except (SQLAlchemyError, TimeoutError) as unreachable:
        logger.error("[ready] the database did not answer: %s", unreachable)

        return JSONResponse(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content=HealthResponse(status="unavailable").model_dump())

    return HealthResponse(status="ok")
