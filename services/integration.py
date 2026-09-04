import secrets

from helpers import brand
from helpers.i18n import translate
from helpers.security import decrypt, encrypt
from models.integration import ExternalProduct, Integration, WebhookEvent
from services.crud import CrudService, Dependent, Reach
from services.gateway import API_KEY, PROVIDERS, WEBHOOK_SECRET


class IntegrationService(CrudService):
    model = Integration
    search_fields = ("webhook_key",)
    filter_fields = ("tenant_id", "provider", "environment", "active")
    ordering_fields = ("id", "provider", "environment", "created_at")
    default_ordering = "-id"
    relations = ("tenant",)
    label_fields = ("provider",)
    dependents = (Dependent(WebhookEvent, "integration_id"), Dependent(ExternalProduct, "integration_id"))

    def build_label(self, instance) -> str:
        """Names an integration by the brand it belongs to and the gateway it talks to, and a brand is what this instance is where it holds no tenant."""
        return f"{brand.of(instance.tenant).name} - {translate(f'enum.provider.{instance.provider.value}')}"

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


class ExternalProductService(CrudService):
    model = ExternalProduct
    reaches_through = Reach(ExternalProduct.integration_id, Integration)
    search_fields = ("external_id", "notes")
    text_search_fields = ("display_name",)
    filter_fields = ("integration_id", "plan_id", "active")
    ordering_fields = ("id", "external_id", "display_name", "created_at")
    default_ordering = "-id"
    relations = ("integration", "plan")
    label_fields = ("display_name", "external_id")

    async def prepare(self, data: dict, instance) -> dict:
        prepared = dict(data)

        if prepared.get("reference_currency"):
            prepared["reference_currency"] = prepared["reference_currency"].upper()

        return prepared


class WebhookEventService(CrudService):
    model = WebhookEvent
    search_fields = ()
    filter_fields = ("tenant_id", "integration_id", "status", "action", "user_id", "subscription_id")
    ordering_fields = ("id", "action", "status", "occurred_at", "created_at")
    default_ordering = "-id"
    relations = ("tenant", "integration")
    label_fields = ("external_event_id",)


integration_service = IntegrationService()
external_product_service = ExternalProductService()
webhook_event_service = WebhookEventService()
