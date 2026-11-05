from fastapi import APIRouter, status

from helpers.auth import CurrentBrand, OptionalBrandAccount
from helpers.crud import build_readonly_router
from helpers.db import DatabaseSession
from schemas.app_event_batch_request import AppEventBatchRequest
from schemas.app_event_batch_response import AppEventBatchResponse
from schemas.app_event_schema import AppEventSchema
from services.app_event_service import app_event_service

public_router = APIRouter(prefix="/events", tags=["events"])


@public_router.post("", response_model=AppEventBatchResponse, status_code=status.HTTP_202_ACCEPTED, summary="Report a batch of app events")
async def ingest(db: DatabaseSession, brand: CurrentBrand, user: OptionalBrandAccount, payload: AppEventBatchRequest):
    accepted, duplicated = await app_event_service.ingest(db, brand, user, [event.model_dump() for event in payload.events])

    return AppEventBatchResponse(accepted=accepted, duplicated=duplicated)


router = build_readonly_router(app_event_service, AppEventSchema, "/app-events", "app events")
