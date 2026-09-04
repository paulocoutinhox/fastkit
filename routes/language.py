from fastapi import APIRouter

from helpers.crud import build_router
from helpers.db import DatabaseSession
from helpers.pagination import CurrentPage, Page
from schemas.language import LanguageCreate, LanguageSchema, LanguageUpdate
from services.language import language_service

public_router = APIRouter(prefix="/languages", tags=["languages"])


@public_router.get("/active", response_model=Page[LanguageSchema], summary="List the languages the apps may offer")
async def list_active_languages(db: DatabaseSession, page: CurrentPage):
    total, items = await language_service.paginate(db, page, {"active": True})

    return Page[LanguageSchema](count=total, limit=page.limit, offset=page.offset, items=[LanguageSchema.model_validate(item) for item in items])


router = build_router(language_service, LanguageSchema, LanguageCreate, LanguageUpdate, "/languages", "languages")
