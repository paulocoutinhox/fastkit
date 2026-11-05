from datetime import datetime
from decimal import Decimal

from enums.normalized_action import NormalizedAction
from enums.webhook_event_status import WebhookEventStatus
from schemas.integration_reference import IntegrationReference
from schemas.tenant_reference import TenantReference
from schemas.timestamp_schema import TimestampSchema


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
