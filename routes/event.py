from fastapi import APIRouter, status

from helpers.auth import CurrentBrand, OptionalUser
from helpers.crud import build_readonly_router
from helpers.db import DatabaseSession
from schemas.event import AppEventBatchRequest, AppEventBatchResponse, AppEventSchema
from services.event import app_event_service

public_router = APIRouter(prefix="/events", tags=["events"])


@public_router.post("", response_model=AppEventBatchResponse, status_code=status.HTTP_202_ACCEPTED, summary="Report a batch of app events")
async def ingest(db: DatabaseSession, brand: CurrentBrand, user: OptionalUser, payload: AppEventBatchRequest):
    accepted, duplicated = await app_event_service.ingest(db, brand, user, [event.model_dump() for event in payload.events])

    return AppEventBatchResponse(accepted=accepted, duplicated=duplicated)


router = build_readonly_router(app_event_service, AppEventSchema, "/app-events", "app events")
