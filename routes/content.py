from fastapi import APIRouter

from helpers import cache
from helpers.auth import CurrentBrand
from helpers.crud import build_router
from helpers.db import DatabaseSession
from helpers.errors import NotFoundError
from helpers.i18n import current_locale
from schemas.content import ContentCategoryCreate, ContentCategorySchema, ContentCategoryUpdate, ContentCreate, ContentSchema, ContentUpdate, PublicContentSchema
from services.content import content_category_service, content_service

public_router = APIRouter(prefix="/contents", tags=["contents"])


@public_router.get("/by-tag/{tag}", response_model=PublicContentSchema, summary="Read a published content by its tag")
async def read_by_tag(db: DatabaseSession, brand: CurrentBrand, tag: str):
    """The page in the language the caller asked for in `Accept-Language`, the way every surface a client reads is chosen."""
    language = current_locale.get()

    async def build():
        content = await content_service.find_by_tag(db, tag, brand.id, language)

        if content is None:
            raise NotFoundError()

        return PublicContentSchema.model_validate(content).model_dump(mode="json")

    return PublicContentSchema(**await cache.answered(cache.content, cache.named(surface="api", tenant=brand.id, language=language, tag=tag), build))


router = build_router(content_service, ContentSchema, ContentCreate, ContentUpdate, "/contents", "contents")
category_router = build_router(content_category_service, ContentCategorySchema, ContentCategoryCreate, ContentCategoryUpdate, "/content-categories", "content categories")
