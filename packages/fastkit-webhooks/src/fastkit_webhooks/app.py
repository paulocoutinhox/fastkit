from fastkit_core.apps.base import BootstrapContext, FastKitApp
from fastkit_webhooks.models import WebhookEvent
from fastkit_webhooks.service import WebhookRegistry, WebhookService


class WebhooksApp(FastKitApp):
    name = "fastkit.webhooks"
    label = "webhooks"
    version = "1.0.0"
    requires = ("fastkit.core", "fastkit.db")

    def register_models(self, context: BootstrapContext) -> None:
        context.models.register(WebhookEvent, source=self.name)

    def register_services(self, context: BootstrapContext) -> None:
        database = context.component("database")
        registry = WebhookRegistry()

        context.set_component("webhook_registry", registry)
        context.set_component("webhook_service", WebhookService(database.session_factory, registry))
