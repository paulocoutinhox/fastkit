from pydantic import computed_field

from enums.environment import Environment
from enums.provider import Provider
from helpers.i18n import translate
from helpers.settings import settings
from schemas.base_schema import BaseSchema
from schemas.tenant_reference import TenantReference


class IntegrationReference(BaseSchema):
    id: int
    provider: Provider
    environment: Environment
    tenant: TenantReference | None

    @computed_field
    @property
    def label(self) -> str:
        """Names an integration by the brand it belongs to and the gateway it talks to, because two brands each hold a Stripe of their own."""
        owner = self.tenant.name if self.tenant else settings.name

        return f"{owner} - {translate(f'enum.provider.{self.provider.value}')}"
