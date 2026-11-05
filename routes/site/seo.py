from fastapi import APIRouter, Request
from starlette.responses import PlainTextResponse, Response

from helpers.dates import as_utc
from helpers.db import DatabaseSession
from helpers.page_not_found import PageNotFound
from helpers.settings import settings
from helpers.site import brand_of, content_path
from services.content_service import content_service
from services.gallery_service import gallery_service
from services.product_service import product_service

# What a crawler is offered, which is every page this process answers on its own. An address a content carries is listed once that content exists.
PUBLIC_PATHS = ("/", "/contact", "/plans", "/products", "/gallery", "/newsletter", "/cookies")

router = APIRouter(include_in_schema=False)


@router.get("/robots.txt")
async def robots(request: Request, db: DatabaseSession):
    """The panel is reached by people who already know where it is, and this is not how they learn."""
    brand = await brand_of(db, request)

    if brand is None:
        raise PageNotFound()

    # The API answers JSON to an application and is no page of the site, so a crawler spends nothing on it.
    body = "\n".join(["User-agent: *", "Allow: /", f"Disallow: {settings.api_path}/", f"Sitemap: {brand.address('/sitemap.xml')}"])

    return PlainTextResponse(body + "\n")


@router.get("/sitemap.xml")
async def sitemap(request: Request, db: DatabaseSession):
    """One address per page, because a page reads in whatever language its visitor chose and is never a second address."""
    brand = await brand_of(db, request)

    if brand is None:
        raise PageNotFound()

    # A page this process draws on its own has no date of its own, and a row says when it last changed, which is what tells a crawler to come back.
    changed = {path: None for path in PUBLIC_PATHS}

    for content in await content_service.list_public(db, brand.id):
        changed.setdefault(content_path(content.tag), content.updated_at)

    for gallery in await gallery_service.list_reachable(db, brand.id):
        changed.setdefault(f"/gallery/{gallery.tag}", gallery.updated_at)

    for product in await product_service.list_reachable(db, brand.id):
        changed.setdefault(f"/products/{product.slug}", product.updated_at)

    entries = "".join(entry(brand.address(path), moment) for path, moment in changed.items())
    body = f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{entries}</urlset>'

    return Response(body, media_type="application/xml")


def entry(address: str, moment) -> str:
    modified = f"<lastmod>{as_utc(moment).isoformat(timespec='seconds')}</lastmod>" if moment else ""

    return f"<url><loc>{address}</loc>{modified}</url>"
