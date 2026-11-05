import asyncio
import logging
from enum import StrEnum

from fastapi import APIRouter, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from starlette.responses import JSONResponse

from enums.app_event_status import AppEventStatus
from enums.authentication_surface import AuthenticationSurface
from enums.banner_placement import BannerPlacement
from enums.benefit_cadence import BenefitCadence
from enums.benefit_grant_status import BenefitGrantStatus
from enums.benefit_policy import BenefitPolicy
from enums.benefit_status import BenefitStatus
from enums.benefit_type import BenefitType
from enums.credit_transaction_type import CreditTransactionType
from enums.environment import Environment
from enums.interval_unit import IntervalUnit
from enums.log_category import LogCategory
from enums.log_level import LogLevel
from enums.missed_cycle_policy import MissedCyclePolicy
from enums.newsletter_status import NewsletterStatus
from enums.normalized_action import NormalizedAction
from enums.outbound_email_status import OutboundEmailStatus
from enums.postal_code_provider import PostalCodeProvider
from enums.provider import Provider
from enums.purchase_status import PurchaseStatus
from enums.resume_delivery_policy import ResumeDeliveryPolicy
from enums.subscription_status import SubscriptionStatus
from enums.user_address_type import UserAddressType
from enums.user_entitlement_status import UserEntitlementStatus
from enums.user_gender import UserGender
from enums.user_role import UserRole
from enums.user_status import UserStatus
from enums.webhook_event_status import WebhookEventStatus
from helpers import captcha, visitor
from helpers.auth import CurrentUser
from helpers.authentication_helper import AuthenticationHelper
from helpers.crud import RESOURCES
from helpers.db import DatabaseSession
from helpers.settings import settings
from schemas.challenge_schema import ChallengeSchema
from schemas.common import TIMEZONES
from schemas.credential_schema import CredentialSchema
from schemas.health_response import HealthResponse
from schemas.meta_response import MetaResponse
from schemas.permissions_response import PermissionsResponse
from schemas.visitor_schema import VisitorSchema
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


@router.get("", response_model=MetaResponse, summary="Read what the admin needs to render its forms")
async def read_meta():
    return MetaResponse(
        name=settings.name,
        environment=settings.environment,
        version=settings.version,
        storage_base_url=settings.storage.base_url,
        enums={name: [member.value for member in enum_class] for name, enum_class in CATALOG.items()},
        provider_credentials={provider.value: [CredentialSchema(field=credential.field, label=credential.label, hint=credential.hint) for credential in gateway.credentials] for provider, gateway in PROVIDERS.items()},
        timezones=TIMEZONES,
        authentication=AuthenticationHelper.methods(AuthenticationSurface.ADMIN),
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
