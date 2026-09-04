from fastapi import APIRouter, Request
from starlette.responses import PlainTextResponse, Response

from helpers.db import DatabaseSession
from helpers.site import PageNotFound, brand_of
from routes.site.pages import NAMED_CONTENT
from services.commerce import product_service
from services.content import content_service
from services.gallery import gallery_service

# What a crawler is offered, which is every page this process answers on its own. An address a content carries is listed once that content exists.
PUBLIC_PATHS = ("/", "/contact", "/plans", "/products", "/gallery", "/newsletter", "/cookies")

router = APIRouter(include_in_schema=False)


@router.get("/robots.txt")
async def robots(request: Request, db: DatabaseSession):
    """The panel is reached by people who already know where it is, and this is not how they learn."""
    brand = await brand_of(db, request)

    if brand is None:
        raise PageNotFound()

    body = "\n".join(["User-agent: *", "Allow: /", f"Sitemap: {brand.address('/sitemap.xml')}"])

    return PlainTextResponse(body + "\n")


@router.get("/sitemap.xml")
async def sitemap(request: Request, db: DatabaseSession):
    """One address per page, because a page reads in whatever language its visitor chose and is never a second address."""
    brand = await brand_of(db, request)

    if brand is None:
        raise PageNotFound()

    paths = list(PUBLIC_PATHS)

    paths += [NAMED_CONTENT.get(content.tag, f"/content/{content.tag}") for content in await content_service.list_reachable(db, brand.id)]
    paths += [f"/gallery/{gallery.tag}" for gallery in await gallery_service.list_reachable(db, brand.id)]
    paths += [f"/products/{product.slug}" for product in await product_service.list_reachable(db, brand.id)]

    entries = "".join(f"<url><loc>{brand.address(path)}</loc></url>" for path in dict.fromkeys(paths))
    body = f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{entries}</urlset>'

    return Response(body, media_type="application/xml")
