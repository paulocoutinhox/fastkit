from models.webhook_event import WebhookEvent
from services.crud_service import CrudService


class WebhookEventService(CrudService):
    model = WebhookEvent
    search_fields = ()
    filter_fields = ("tenant_id", "integration_id", "status", "action", "user_id", "subscription_id")
    ordering_fields = ("id", "action", "status", "occurred_at", "created_at")
    default_ordering = "-id"
    relations = ("tenant", "integration.tenant")
    label_fields = ("external_event_id",)


webhook_event_service = WebhookEventService()
