from fastapi import APIRouter, Form, Request
from starlette.responses import RedirectResponse

from enums.banner import BannerPlacement
from enums.consent import ConsentCategory
from enums.newsletter import NewsletterStatus
from enums.theme import Theme
from helpers import cache, captcha, consent, visitor
from helpers.consent import Consent
from helpers.db import DatabaseSession
from helpers.errors import NotFoundError
from helpers.forms import validated
from helpers.settings import settings
from helpers.site import NAMED_CONTENT, PageNotFound, inside, notice, owned_elsewhere, redirect, remember_preference, render, structured_data
from helpers.storage import storage
from routes.newsletter import confirmation_link
from routes.site.base import CsrfToken, CurrentPage, guard, refused_by_captcha
from schemas.commerce import CatalogEntrySchema, product_card
from schemas.contact import ContactRequest
from schemas.newsletter import NewsletterRequest
from schemas.subscription import CatalogPlanSchema, catalogued
from services.banner import banner_service
from services.commerce import product_service, user_product_service
from services.contact import contact_service
from services.content import content_service
from services.gallery import gallery_photo_service, gallery_service
from services.newsletter import newsletter_subscription_service
from services.subscription import plan_service

router = APIRouter(include_in_schema=False)


async def gallery_cards(db, galleries: list) -> list[dict]:
    """The cards for the galleries the caller decided to draw, whose covers are read in one query and never one apiece."""
    covers = await gallery_photo_service.covers_for(db, [gallery.id for gallery in galleries])

    return [{"uuid": gallery.uuid, "title": gallery.title, "tag": gallery.tag, "description": gallery.description, "cover_url": storage.url(covers[gallery.id]) if gallery.id in covers else None} for gallery in galleries]


def offered(plan) -> dict:
    return catalogued(plan).model_dump(mode="json")


@router.get("/")
async def home(page: CurrentPage, db: DatabaseSession):
    async def build():
        banners = await banner_service.list_active(db, page.brand.id, BannerPlacement.HOME, language=page.language)
        products = await product_service.list_reachable(db, page.brand.id)
        plans = await plan_service.list_offered(db, page.brand.id, page.language)

        # The home draws three, so it asks for the covers of three and not of every gallery the tenant has.
        galleries = (await gallery_service.list_reachable(db, page.brand.id, page.language))[:3]

        return {
            "banners": [{"uuid": banner.uuid, "title": banner.title, "url": banner.url, "image_url": storage.url(banner.image) if banner.image else None} for banner in banners],
            "products": [product_card(product).model_dump(mode="json") for product in products if product.featured][:6],
            "plans": [offered(plan) for plan in plans if plan.featured] or [offered(plan) for plan in plans],
            "galleries": await gallery_cards(db, galleries),
        }

    assembled = await cache.answered(cache.home, cache.named(surface="site", tenant=page.brand.id, language=page.language), build)
    assembled = assembled | {"products": [CatalogEntrySchema(**entry) for entry in assembled["products"]], "plans": [CatalogPlanSchema(**entry) for entry in assembled["plans"]]}

    # The absolute address in structured data belongs to this request, so it never enters a value shared between hosts or schemes.
    return render(page, "pages/home.html", assembled | {"organization": structured_data(page.brand)})


# A tag with an address of its own, which is the only address it is ever read at.
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
    refused = errors | await refused_by_captcha(page, captcha_answer, captcha_token)

    if refused:
        return render(page, "pages/contact.html", {"challenge": captcha.issue(), "values": values, "errors": refused}, status_code=422)

    await contact_service.send(db, page.brand, payload.name, payload.email, payload.message)

    return redirect("/contact", [notice("site.contact-sent")])


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
async def products(page: CurrentPage, db: DatabaseSession):
    async def build():
        return [product_card(product).model_dump(mode="json") for product in await product_service.list_reachable(db, page.brand.id, None)]

    items = await cache.answered(cache.products, cache.named(surface="site", tenant=page.brand.id, language=page.language), build)

    return render(page, "pages/products.html", {"products": [CatalogEntrySchema(**entry) for entry in items]})


@router.get("/products/{slug}")
async def product(page: CurrentPage, db: DatabaseSession, slug: str):
    async def build():
        found = await product_service.find_reachable(db, page.brand.id, slug)

        if found is None:
            raise PageNotFound()

        return product_card(found).model_dump(mode="json")

    found = await cache.answered(cache.products, cache.named(surface="site", tenant=page.brand.id, language=page.language, slug=slug), build)

    # Owning is of one account and the cached card is everybody's, so it is asked for each reader after the card is read.
    owned = page.user is not None and await user_product_service.owned_by(db, page.user.id, found["id"])

    return render(page, "pages/product.html", {"product": CatalogEntrySchema(**found), "owned": owned})


@router.get("/newsletter")
async def newsletter(page: CurrentPage):
    return render(page, "pages/newsletter.html", {"challenge": captcha.issue(), "values": {}, "errors": {}})


@router.post("/newsletter")
async def subscribe_newsletter(page: CurrentPage, db: DatabaseSession, csrf_token: CsrfToken = None, email: str = Form(""), captcha_answer: str = Form(""), captcha_token: str = Form("")):
    """An address is written down as pending and hears nothing until it answers the confirmation, so nobody signs anybody else up."""
    guard(page, csrf_token)

    values = {"email": email}
    payload, errors = validated(NewsletterRequest, values)
    refused = errors | await refused_by_captcha(page, captcha_answer, captcha_token)

    if refused:
        return render(page, "pages/newsletter.html", {"challenge": captcha.issue(), "values": values, "errors": refused}, status_code=422)

    await newsletter_subscription_service.subscribe(db, page.brand, payload.email, confirmation_link(page.brand))

    return redirect("/", [notice("site.newsletter-sent")])


# What each link of a newsletter letter asks, and what answering it does.
NEWSLETTER_ANSWERS = {
    "confirm": (NewsletterStatus.CONFIRMED, "site.newsletter-confirm-title", "site.newsletter-confirm-lead", "site.newsletter-confirm-button", "site.newsletter-confirmed"),
    "unsubscribe": (NewsletterStatus.UNSUBSCRIBED, "site.newsletter-unsubscribe-title", "site.newsletter-unsubscribe-lead", "site.newsletter-unsubscribe-button", "site.newsletter-unsubscribed"),
}


@router.get("/newsletter/confirm/{token}")
async def confirm_newsletter_question(page: CurrentPage, db: DatabaseSession, token: str):
    return await newsletter_question(page, db, token, "confirm")


@router.post("/newsletter/confirm/{token}")
async def confirm_newsletter(page: CurrentPage, db: DatabaseSession, token: str, csrf_token: CsrfToken = None):
    guard(page, csrf_token)

    return await settle_newsletter(page, db, token, "confirm")


@router.get("/newsletter/unsubscribe/{token}")
async def unsubscribe_newsletter_question(page: CurrentPage, db: DatabaseSession, token: str):
    return await newsletter_question(page, db, token, "unsubscribe")


@router.post("/newsletter/unsubscribe/{token}")
async def unsubscribe_newsletter(page: CurrentPage, db: DatabaseSession, token: str, csrf_token: CsrfToken = None):
    guard(page, csrf_token)

    return await settle_newsletter(page, db, token, "unsubscribe")


async def subscription_of(page, db, token: str):
    """The token is the address proving it is the address, so a link that names nothing is a page that does not exist."""
    found = await newsletter_subscription_service.find_by_token(db, token)

    if found is None or found.tenant_id != page.brand.id:
        raise PageNotFound()

    return found


async def newsletter_question(page, db, token: str, answer: str):
    """A mail client and the scanner in front of it open a link on their own, so the link asks and only the answer sent from the page changes anything."""
    await subscription_of(page, db, token)
    _, heading, lead, button, _ = NEWSLETTER_ANSWERS[answer]

    return render(page, "pages/answer.html", {"heading": heading, "lead": lead, "button": button, "next": None})


async def settle_newsletter(page, db, token: str, answer: str):
    found = await subscription_of(page, db, token)
    status, _, _, _, message = NEWSLETTER_ANSWERS[answer]

    await newsletter_subscription_service.settle(db, found, status)

    return redirect("/", [notice(message)])


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

    # Only a choice somebody made is rewritten: writing the language the browser happened to ask for would turn it into a choice nobody made.
    if settings.site.language_cookie in page.request.cookies:
        remember_preference(answer, settings.site.language_cookie, page.language, settled)

    if settings.site.theme_cookie in page.request.cookies:
        remember_preference(answer, settings.site.theme_cookie, page.theme.value, settled)

    # Counting a reader is what the analytics category names, so withdrawing it takes the name away instead of keeping it unused.
    if ConsentCategory.ANALYTICS in allowed:
        visitor.remember(answer, visitor.carried(page.request))
    else:
        visitor.forget(answer)

    return answer


@router.post("/language")
async def choose_language(page: CurrentPage, csrf_token: CsrfToken = None, language: str = Form(""), next_path: str = Form("/", alias="next")):
    """The language the pages are read in, kept in a cookie: the language of the messages an account receives is chosen on its profile, and this never touches it."""
    guard(page, csrf_token)

    if language not in settings.languages:
        raise PageNotFound()

    answer = RedirectResponse(inside(next_path), status_code=303)
    remember_preference(answer, settings.site.language_cookie, language, page.consent)

    return answer


@router.post("/theme")
async def choose_theme(page: CurrentPage, csrf_token: CsrfToken = None, theme: str = Form(""), next_path: str = Form("/", alias="next")):
    """The palette follows the person and not the address, so the page is one address however it is drawn."""
    guard(page, csrf_token)

    if theme not in set(Theme):
        raise PageNotFound()

    answer = RedirectResponse(inside(next_path), status_code=303)
    remember_preference(answer, settings.site.theme_cookie, Theme(theme).value, page.consent)

    return answer


@router.get("/{path:path}")
async def anything_else(request: Request, path: str):
    """The site takes what is left, and a path of the API is an error and never a page dressed as a success."""
    if owned_elsewhere(request):
        raise NotFoundError()

    raise PageNotFound()
