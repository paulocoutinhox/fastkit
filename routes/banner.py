from fastapi import APIRouter, Query, Request, Response

from enums.banner_count_kind import BannerCountKind
from enums.banner_placement import BannerPlacement
from helpers import cache, visitor
from helpers.auth import CurrentBrand
from helpers.brand import Brand
from helpers.crud import build_router
from helpers.db import DatabaseSession, commit
from helpers.i18n import current_locale
from helpers.not_found_error import NotFoundError
from helpers.storage import storage
from schemas.active_banner_schema import ActiveBannerSchema
from schemas.banner_count_request import BannerCountRequest
from schemas.banner_create import BannerCreate
from schemas.banner_list_response import BannerListResponse
from schemas.banner_schema import BannerSchema
from schemas.banner_update import BannerUpdate
from services.banner_service import banner_service

public_router = APIRouter(prefix="/banners", tags=["banners"])


@public_router.get("/active", response_model=BannerListResponse, summary="List the banners live right now")
async def list_active(db: DatabaseSession, brand: CurrentBrand, placement: BannerPlacement | None = Query(None)):
    language = current_locale.get()

    async def build():
        items = await banner_service.list_active(db, brand.id, placement, language)

        return [ActiveBannerSchema(uuid=item.uuid, placement=item.placement, title=item.title, image_url=storage.url(item.image) if item.image else None, url=item.url, position=item.position).model_dump(mode="json") for item in items]

    entries = await cache.answered(cache.banners, cache.named(surface="api", tenant=brand.id, language=language, placement=placement), build)

    return BannerListResponse(items=[ActiveBannerSchema(**entry) for entry in entries])


async def settle_count(db, brand: Brand, request: Request, uuid: str, body: BannerCountRequest, kind: BannerCountKind) -> Response:
    """A count nobody may be named for is not an error, because whether a reader allowed one is never the business of the caller."""
    banner = await banner_service.find_by_uuid(db, uuid, brand.id)

    if banner is None:
        raise NotFoundError()

    # A browser carries the name in a cookie the page cannot read, and an application carries it in the body.
    who = visitor.counted(request) or visitor.named(body.visitor)

    if who is not None:
        await banner_service.count(db, banner, kind, who)
        await commit(db)

    return Response(status_code=204)


@public_router.post("/{uuid}/view", status_code=204, summary="Count that a banner was seen")
async def count_view(db: DatabaseSession, brand: CurrentBrand, request: Request, uuid: str, body: BannerCountRequest = BannerCountRequest()):
    return await settle_count(db, brand, request, uuid, body, BannerCountKind.VIEW)


@public_router.post("/{uuid}/click", status_code=204, summary="Count that a banner was followed")
async def count_click(db: DatabaseSession, brand: CurrentBrand, request: Request, uuid: str, body: BannerCountRequest = BannerCountRequest()):
    return await settle_count(db, brand, request, uuid, body, BannerCountKind.CLICK)


router = build_router(banner_service, BannerSchema, BannerCreate, BannerUpdate, "/banners", "banners")
