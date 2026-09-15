from fastapi import APIRouter, Request

from enums.integration import WebhookEventStatus
from helpers.db import DatabaseSession
from helpers.errors import NotFoundError
from schemas.integration import WebhookReceipt
from services.gateway import InboundCall
from services.webhook import webhook_service

# A gateway decides how it calls, so every method is answered and nothing about the body is demanded before it is read.
METHODS = ("GET", "POST", "PUT", "PATCH", "DELETE")

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


async def receive(request: Request, db: DatabaseSession, key: str):
    """The key in the address says which tenant and which gateway is calling, and that gateway is what reads the rest."""
    integration = await webhook_service.find_integration(db, key)

    if integration is None:
        raise NotFoundError()

    call = InboundCall(method=request.method, headers=dict(request.headers), query=dict(request.query_params), body=await request.body())

    if call.is_empty():
        return WebhookReceipt(status=WebhookEventStatus.IGNORED, action=None)

    event = await webhook_service.ingest(db, integration, call)

    return WebhookReceipt(status=event.status, action=event.action)


# One handler under every method, each named apart: a single route would answer them all under one operation id.
for method in METHODS:
    router.add_api_route("/{key}", receive, methods=[method], response_model=WebhookReceipt, operation_id=f"receive_webhook_{method.lower()}", summary="Receive what a payment gateway reports for one tenant")
