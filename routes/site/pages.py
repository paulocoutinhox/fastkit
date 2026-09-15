from fastapi import APIRouter, Form, Query, Request
from pydantic import EmailStr, Field
from starlette.responses import RedirectResponse

from enums.consent import ConsentCategory
from enums.newsletter import NewsletterStatus
from enums.theme import Theme
from helpers import cache, captcha, consent, visitor
from helpers.consent import Consent
from helpers.db import DatabaseSession
from helpers.errors import NotFoundError
from helpers.forms import validated
from helpers.settings import settings
from helpers.site import PageNotFound, inside, notice, owned_elsewhere, redirect, remember_language, remember_theme, render, structured_data
from helpers.storage import storage
from routes.newsletter import confirmation_link
from routes.site.base import CsrfToken, CurrentPage, guard, refused_by_captcha
from schemas.commerce import SiteProductSchema
from schemas.common import BaseSchema
from schemas.subscription import CatalogPlanSchema, catalogued
from services.banner import banner_service
from services.commerce import product_service
from services.contact import contact_service
from services.content import content_service
from services.gallery import gallery_photo_service, gallery_service
from services.language import language_service
from services.newsletter import newsletter_subscription_service
from services.subscription import plan_service
from services.user import user_service

router = APIRouter(include_in_schema=False)


class NewsletterRequest(BaseSchema):
    email: EmailStr = Field(max_length=320)


class ContactRequest(BaseSchema):
    name: str = Field(min_length=2, max_length=128)
    email: EmailStr = Field(max_length=255)
    message: str = Field(min_length=10, max_length=4000)


def presented(product) -> dict:
    return SiteProductSchema(
        id=product.id,
        uuid=product.uuid,
        name=product.name,
        slug=product.slug,
        description=product.description,
        image_url=storage.url(product.image) if product.image else None,
        currency=product.currency,
        price=product.price,
        credits=product.credits,
        credits_currency=product.credits_currency.name if product.credits_currency else None,
    ).model_dump(mode="json")


async def gallery_cards(db, galleries: list) -> list[dict]:
    """The cards for the galleries the caller decided to draw, whose covers are read in one query and never one apiece."""
    covers = await gallery_photo_service.covers_for(db, [gallery.id for gallery in galleries])

    return [{"uuid": gallery.uuid, "title": gallery.title, "tag": gallery.tag, "description": gallery.description, "cover_url": storage.url(covers[gallery.id]) if gallery.id in covers else None} for gallery in galleries]


def offered(plan) -> dict:
    return catalogued(plan).model_dump(mode="json")


@router.get("/")
async def home(page: CurrentPage, db: DatabaseSession):
    async def build():
        banners = await banner_service.list_active(db, page.brand.id, language=page.language)
        products = await product_service.list_reachable(db, page.brand.id)
        plans = await plan_service.list_offered(db, page.brand.id, page.language)

        # The home draws three, so it asks for the covers of three and not of every gallery the tenant has.
        galleries = (await gallery_service.list_reachable(db, page.brand.id, page.language))[:3]

        return {
            "banners": [{"uuid": banner.uuid, "title": banner.title, "url": banner.url, "image_url": storage.url(banner.image) if banner.image else None} for banner in banners],
            "products": [presented(product) for product in products if product.featured][:6],
            "plans": [offered(plan) for plan in plans if plan.featured] or [offered(plan) for plan in plans],
            "galleries": await gallery_cards(db, galleries),
        }

    assembled = await cache.answered(cache.home, cache.named(surface="site", tenant=page.brand.id, language=page.language), build)
    assembled = assembled | {"products": [SiteProductSchema(**entry) for entry in assembled["products"]], "plans": [CatalogPlanSchema(**entry) for entry in assembled["plans"]]}

    # The absolute address in structured data belongs to this request, so it never enters a value shared between hosts or schemes.
    return render(page, "pages/home.html", assembled | {"organization": structured_data(page.brand)})


# A tag with an address of its own, which is the only address it is ever read at.
NAMED_CONTENT = {"about": "/about"}


@router.get("/about")
async def about(page: CurrentPage, db: DatabaseSession):
    """A named address for one tag, because `/about` is what a person types and what a crawler expects to find."""
    return await content_page(page, db, "about")


@router.get("/contact")
async def contact(page: CurrentPage):
    return render(page, "pages/contact.html", {"challenge": captcha.issue(), "values": {}, "errors": {}})


@router.post("/contact")
async def send_contact(page: CurrentPage, db: DatabaseSession, csrf_token: CsrfToken = None, name: str = Form(""), email: str = Form(""), message: str = Form(""), captcha_answer: str = Form(""), captcha_token: str = Form("")):
    guard(page, csrf_token)

    values = {"name": name, "email": email, "message": message}
    payload, errors = validated(ContactRequest, values)
    refused = (errors or {}) | await refused_by_captcha(page, captcha_answer, captcha_token)

    if refused:
        return render(page, "pages/contact.html", {"challenge": captcha.issue(), "values": values, "errors": refused}, status_code=422)

    await contact_service.send(db, page.brand, payload.name, payload.email, payload.message)

    return redirect(page, "/contact", [notice("site.contact-sent")])


@router.get("/content/{tag}")
async def content(page: CurrentPage, db: DatabaseSession, tag: str):
    """A tag that has an address of its own is read there and nowhere else, or the same page would be two addresses."""
    if tag in NAMED_CONTENT:
        return RedirectResponse(NAMED_CONTENT[tag], status_code=301)

    return await content_page(page, db, tag)


async def content_page(page, db, tag: str):
    async def build():
        found = await content_service.find_by_tag(db, tag, page.brand.id, page.language)

        if found is None:
            raise PageNotFound()

        return {"uuid": found.uuid, "title": found.title, "content": found.content}

    content = await cache.answered(cache.content, cache.named(surface="site", tenant=page.brand.id, language=page.language, tag=tag), build)

    return render(page, "pages/content.html", {"content": content})


@router.get("/gallery")
async def galleries(page: CurrentPage, db: DatabaseSession):
    async def build():
        return await gallery_cards(db, await gallery_service.list_reachable(db, page.brand.id, page.language))

    items = await cache.answered(cache.gallery, cache.named(surface="site", tenant=page.brand.id, language=page.language), build)

    return render(page, "pages/gallery-list.html", {"galleries": items})


@router.get("/gallery/{tag}")
async def gallery(page: CurrentPage, db: DatabaseSession, tag: str):
    async def build():
        found = await gallery_service.find_by_tag(db, tag, page.brand.id, page.language)

        if found is None:
            raise PageNotFound()

        photos = await gallery_photo_service.list_of(db, found.id)

        return {"gallery": {"uuid": found.uuid, "title": found.title, "description": found.description}, "photos": [{"uuid": photo.uuid, "caption": photo.caption, "image_url": storage.url(photo.image)} for photo in photos]}

    assembled = await cache.answered(cache.gallery, cache.named(surface="site", tenant=page.brand.id, language=page.language, tag=tag), build)

    return render(page, "pages/gallery.html", assembled)


@router.get("/plans")
async def plans(page: CurrentPage, db: DatabaseSession):
    async def build():
        return [offered(plan) for plan in await plan_service.list_offered(db, page.brand.id, page.language)]

    items = await cache.answered(cache.plans, cache.named(surface="site", tenant=page.brand.id, language=page.language), build)

    return render(page, "pages/plans.html", {"plans": [CatalogPlanSchema(**entry) for entry in items]})


@router.get("/products")
async def products(page: CurrentPage, db: DatabaseSession, search: str | None = Query(None, max_length=128)):
    term = (search or "").strip() or None

    async def build():
        return [presented(product) for product in await product_service.list_reachable(db, page.brand.id, term)]

    items = await cache.answered(cache.search if term else cache.products, cache.named(surface="site", tenant=page.brand.id, language=page.language, search=term), build)

    return render(page, "pages/products.html", {"products": [SiteProductSchema(**entry) for entry in items]})


@router.get("/products/{slug}")
async def product(page: CurrentPage, db: DatabaseSession, slug: str):
    async def build():
        found = await product_service.find_reachable(db, page.brand.id, slug)

        if found is None:
            raise PageNotFound()

        return presented(found)

    found = await cache.answered(cache.products, cache.named(surface="site", tenant=page.brand.id, language=page.language, slug=slug), build)

    return render(page, "pages/product.html", {"product": SiteProductSchema(**found)})


@router.get("/newsletter")
async def newsletter(page: CurrentPage):
    return render(page, "pages/newsletter.html", {"challenge": captcha.issue(), "values": {}, "errors": {}})


@router.post("/newsletter")
async def subscribe_newsletter(page: CurrentPage, db: DatabaseSession, csrf_token: CsrfToken = None, email: str = Form(""), captcha_answer: str = Form(""), captcha_token: str = Form("")):
    """An address is written down as pending and hears nothing until it answers the confirmation, so nobody signs anybody else up."""
    guard(page, csrf_token)

    values = {"email": email}
    payload, errors = validated(NewsletterRequest, values)
    refused = (errors or {}) | await refused_by_captcha(page, captcha_answer, captcha_token)

    if refused:
        return render(page, "pages/newsletter.html", {"challenge": captcha.issue(), "values": values, "errors": refused}, status_code=422)

    await newsletter_subscription_service.subscribe(db, page.brand, payload.email, confirmation_link(page.brand))

    return redirect(page, "/", [notice("site.newsletter-sent")])


@router.get("/newsletter/confirm/{token}")
async def confirm_newsletter(page: CurrentPage, db: DatabaseSession, token: str):
    return await settle_newsletter(page, db, token, NewsletterStatus.CONFIRMED, "site.newsletter-confirmed")


@router.get("/newsletter/unsubscribe/{token}")
async def unsubscribe_newsletter(page: CurrentPage, db: DatabaseSession, token: str):
    return await settle_newsletter(page, db, token, NewsletterStatus.UNSUBSCRIBED, "site.newsletter-unsubscribed")


async def settle_newsletter(page, db, token: str, status: NewsletterStatus, message: str):
    """The token is the address proving it is the address, so a link that names nothing is a page that does not exist."""
    found = await newsletter_subscription_service.find_by_token(db, token)

    if found is None or found.tenant_id != page.brand.id:
        raise PageNotFound()

    await newsletter_subscription_service.settle(db, found, status)

    return redirect(page, "/", [notice(message)])


@router.get("/cookies")
async def cookies(page: CurrentPage):
    """Withdrawing has to be as easy as giving, so the answer has a page of its own and not only a banner."""
    return render(page, "pages/cookies.html")


@router.post("/cookies")
async def settle_cookies(page: CurrentPage, csrf_token: CsrfToken = None, action: str = Form(""), next_path: str = Form("/", alias="next")):
    """Allowing everything and refusing everything are one click each, and choosing between them is the same form."""
    guard(page, csrf_token)

    answer = RedirectResponse(inside(next_path), status_code=303)
    allowed = consent.wanted(await page.request.form(), action)

    consent.remember(answer, allowed)

    # The answer decides how long a cookie of preference lives, so the ones already written are rewritten under it.
    settled = Consent(allowed=frozenset(allowed), answered=True)

    remember_language(answer, page.language, settled)
    remember_theme(answer, page.theme, settled)

    # Counting a reader is what the analytics category names, so withdrawing it takes the name away instead of keeping it unused.
    if ConsentCategory.ANALYTICS in allowed:
        visitor.remember(answer, visitor.carried(page.request))
    else:
        visitor.forget(answer)

    return answer


@router.post("/language")
async def choose_language(page: CurrentPage, db: DatabaseSession, csrf_token: CsrfToken = None, language: str = Form(""), next_path: str = Form("/", alias="next")):
    """The choice follows the person rather than the address, so it is kept on the account when there is one and in a cookie when there is not."""
    guard(page, csrf_token)

    if language not in settings.languages:
        raise PageNotFound()

    if page.user is not None:
        chosen = await language_service.find_by_code(db, language)
        await user_service.update(db, page.user.id, {"language_id": chosen.id if chosen else None})

    answer = RedirectResponse(inside(next_path), status_code=303)
    remember_language(answer, language, page.consent)

    return answer


@router.post("/theme")
async def choose_theme(page: CurrentPage, csrf_token: CsrfToken = None, theme: str = Form(""), next_path: str = Form("/", alias="next")):
    """The palette follows the person and not the address, so the page is one address however it is drawn."""
    guard(page, csrf_token)

    if theme not in set(Theme):
        raise PageNotFound()

    answer = RedirectResponse(inside(next_path), status_code=303)
    remember_theme(answer, Theme(theme), page.consent)

    return answer


@router.get("/{path:path}")
async def anything_else(request: Request, path: str):
    """The site takes what is left, and a path of the API is an error and never a page dressed as a success."""
    if owned_elsewhere(request):
        raise NotFoundError()

    raise PageNotFound()
