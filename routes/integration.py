from helpers.crud import build_readonly_router, build_router
from schemas.external_product_create import ExternalProductCreate
from schemas.external_product_schema import ExternalProductSchema
from schemas.external_product_update import ExternalProductUpdate
from schemas.integration_create import IntegrationCreate
from schemas.integration_schema import IntegrationSchema
from schemas.integration_update import IntegrationUpdate
from schemas.webhook_event_schema import WebhookEventSchema
from services.external_product_service import external_product_service
from services.integration_service import integration_service
from services.webhook_event_service import webhook_event_service

router = build_router(integration_service, IntegrationSchema, IntegrationCreate, IntegrationUpdate, "/integrations", "integrations")
external_product_router = build_router(external_product_service, ExternalProductSchema, ExternalProductCreate, ExternalProductUpdate, "/external-products", "external products")
webhook_event_router = build_readonly_router(webhook_event_service, WebhookEventSchema, "/webhook-events", "webhook events")
