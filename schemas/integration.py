from datetime import datetime
from decimal import Decimal

from pydantic import Field

from enums.integration import Environment, NormalizedAction, Provider, WebhookEventStatus
from schemas.common import FREE_TEXT_MAX, BaseSchema, OptionalReference, Reference, Text, TimestampSchema, as_optional
from schemas.subscription import PlanReference
from schemas.tenant import TenantReference


class WebhookReceipt(BaseSchema):
    """What the provider reads back: whether the event was taken, ignored or already known."""

    status: WebhookEventStatus
    action: NormalizedAction | None


class IntegrationReference(BaseSchema):
    id: int
    provider: Provider
    environment: Environment


class IntegrationSchema(TimestampSchema):
    id: int
    tenant_id: int | None
    tenant: TenantReference | None
    provider: Provider
    environment: Environment
    webhook_key: str
    has_revenuecat_api_key: bool
    has_revenuecat_webhook_secret: bool
    has_stripe_api_key: bool
    has_stripe_webhook_secret: bool
    active: bool
    meta: dict


class IntegrationCreate(BaseSchema):
    tenant_id: OptionalReference
    provider: Provider
    environment: Environment = Environment.PRODUCTION
    revenuecat_api_key: str | None = Field(None, max_length=512)
    revenuecat_webhook_secret: str | None = Field(None, max_length=512)
    stripe_api_key: str | None = Field(None, max_length=512)
    stripe_webhook_secret: str | None = Field(None, max_length=512)
    active: bool = True
    meta: dict = Field(default_factory=dict)


IntegrationUpdate = as_optional("IntegrationUpdate", IntegrationCreate)


class ExternalProductSchema(TimestampSchema):
    id: int
    integration_id: int
    integration: IntegrationReference | None
    plan_id: int
    plan: PlanReference | None
    external_id: str
    display_name: str | None
    reference_currency: str | None
    reference_price: Decimal | None
    notes: str | None
    active: bool
    meta: dict


class ExternalProductCreate(BaseSchema):
    integration_id: Reference
    plan_id: Reference
    external_id: Text(191)
    display_name: str | None = Field(None, max_length=255)
    reference_currency: str | None = Field(None, max_length=3)
    reference_price: Decimal | None = Field(None, ge=0)
    notes: str | None = Field(None, max_length=FREE_TEXT_MAX)
    active: bool = True
    meta: dict = Field(default_factory=dict)


ExternalProductUpdate = as_optional("ExternalProductUpdate", ExternalProductCreate)


class WebhookEventSchema(TimestampSchema):
    id: int
    tenant_id: int | None
    tenant: TenantReference | None
    integration_id: int
    integration: IntegrationReference | None
    user_id: int | None
    subscription_id: int | None
    external_event_id: str
    payload_hash: str
    action: NormalizedAction | None
    payload: dict
    amount: Decimal | None
    currency: str | None
    occurred_at: datetime | None
    processed_at: datetime | None
    status: WebhookEventStatus
    error_code: str | None
    error_message: str | None
    attempts: int
    meta: dict
