import secrets

from helpers.security import decrypt, encrypt
from models.external_product import ExternalProduct
from models.integration import Integration
from models.webhook_event import WebhookEvent
from schemas.integration_reference import IntegrationReference
from services.crud_service import CrudService
from services.dependent import Dependent
from services.gateway import PROVIDERS
from services.revenue_cat_provider import API_KEY, WEBHOOK_SECRET


class IntegrationService(CrudService):
    model = Integration
    shared = True
    search_fields = ("webhook_key",)
    filter_fields = ("tenant_id", "provider", "environment", "active")
    ordering_fields = ("id", "provider", "environment", "created_at")
    default_ordering = "-id"
    relations = ("tenant",)
    label_fields = ("provider",)
    dependents = (Dependent(WebhookEvent, "integration_id"), Dependent(ExternalProduct, "integration_id"))

    def build_label(self, instance) -> str:
        return IntegrationReference.model_validate(instance).label

    async def prepare(self, data: dict, instance) -> dict:
        """Secrets arrive in the clear and are never stored or returned that way."""
        prepared = dict(data)

        # The address a provider posts to is born with the integration, because there is no integration without one.
        if instance is None:
            prepared["webhook_key"] = secrets.token_urlsafe(32)

        for name in [name for name in list(prepared) if hasattr(Integration, f"{name}_encrypted")]:
            prepared[f"{name}_encrypted"] = encrypt(prepared.pop(name))

        return prepared

    def column_of(self, integration: Integration, role: str) -> str | None:
        """The gateway says which of its own credentials plays this part, so nothing here knows one by name."""
        named = [credential.field for credential in PROVIDERS[integration.provider].credentials if credential.role == role]

        return f"{named[0]}_encrypted" if named else None

    def read_credential(self, integration: Integration, role: str) -> str | None:
        column = self.column_of(integration, role)

        return decrypt(getattr(integration, column)) if column else None

    def read_secret(self, integration: Integration) -> str | None:
        return self.read_credential(integration, API_KEY)

    def read_webhook_secret(self, integration: Integration) -> str | None:
        return self.read_credential(integration, WEBHOOK_SECRET)


integration_service = IntegrationService()
