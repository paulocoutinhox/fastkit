from fastapi import APIRouter

from helpers.crud import build_router
from helpers.db import DatabaseSession
from schemas.language import LanguageCreate, LanguageSchema, LanguageUpdate
from services.language import language_service

public_router = APIRouter(prefix="/languages", tags=["languages"])


@public_router.get("/active", response_model=list[LanguageSchema], summary="List the languages the apps may offer")
async def list_offered_languages(db: DatabaseSession):
    """The languages an account may keep, which is what this instance offers and never more, so an application cannot pick one the account is then refused."""
    return [LanguageSchema.model_validate(language) for language in await language_service.offered(db)]


router = build_router(language_service, LanguageSchema, LanguageCreate, LanguageUpdate, "/languages", "languages")
