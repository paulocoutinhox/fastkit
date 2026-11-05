from pydantic import Field

from enums.environment import Environment
from enums.provider import Provider
from schemas.base_schema import BaseSchema
from schemas.common import JsonMap, OptionalReference


class IntegrationCreate(BaseSchema):
    tenant_id: OptionalReference
    provider: Provider
    environment: Environment = Environment.PRODUCTION
    revenuecat_api_key: str | None = Field(None, max_length=512)
    revenuecat_webhook_secret: str | None = Field(None, max_length=512)
    stripe_api_key: str | None = Field(None, max_length=512)
    stripe_webhook_secret: str | None = Field(None, max_length=512)
    active: bool = True
    meta: JsonMap = Field(default_factory=dict)
