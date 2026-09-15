from helpers.crud import build_readonly_router, build_router
from schemas.integration import ExternalProductCreate, ExternalProductSchema, ExternalProductUpdate, IntegrationCreate, IntegrationSchema, IntegrationUpdate, WebhookEventSchema
from services.integration import external_product_service, integration_service, webhook_event_service

router = build_router(integration_service, IntegrationSchema, IntegrationCreate, IntegrationUpdate, "/integrations", "integrations")
external_product_router = build_router(external_product_service, ExternalProductSchema, ExternalProductCreate, ExternalProductUpdate, "/external-products", "external products")
webhook_event_router = build_readonly_router(webhook_event_service, WebhookEventSchema, "/webhook-events", "webhook events")
