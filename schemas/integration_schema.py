from enums.environment import Environment
from enums.provider import Provider
from schemas.tenant_reference import TenantReference
from schemas.timestamp_schema import TimestampSchema


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
