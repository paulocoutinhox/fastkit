from typing import Annotated

from fastapi import Depends, Form, Request
from starlette.responses import PlainTextResponse, Response

from helpers import cache, captcha, consent, csrf
from helpers.db import AsyncSessionLocal, DatabaseSession
from helpers.i18n import current_locale, translate
from helpers.site import NAVIGATION, Page, PageExpired, PageNotFound, SignInRequired, account_of, brand_of, chosen_language, chosen_theme, owned_elsewhere, render, taken
from services.content import content_service


async def page_of(db, request: Request) -> Page | None:
    """The one place a page of the site is built, the drawn not found and error pages included, so the brand, the language, the session, the answer about cookies and the navigation are settled once."""
    brand = await brand_of(db, request)

    if brand is None:
        return None

    user = await account_of(db, request, brand)
    language = chosen_language(request)

    # An address of the site says nothing about language, so what the person chose is what the page is rendered in.
    current_locale.set(language)

    async def answered():
        return sorted(await content_service.tags_that_answer(db, tuple(NAVIGATION), brand.id, language))

    drawn = await cache.answered(cache.content, cache.named(surface="navigation", tenant=brand.id, language=language), answered)

    return Page(request=request, brand=brand, language=language, user=user, flashes=taken(request), csrf_token=csrf.issue(request), consent=consent.given(request), theme=chosen_theme(request), pages=frozenset(drawn))


async def get_page(request: Request, db: DatabaseSession) -> Page:
    page = await page_of(db, request)

    if page is None:
        raise PageNotFound()

    return page


async def drawn(request: Request, template: str, status_code: int) -> Response | None:
    """A page of the site the visitor lands on instead of a body written for a client, and nothing at all where the address belongs elsewhere."""
    if owned_elsewhere(request):
        return None

    async with AsyncSessionLocal() as session:
        page = await page_of(session, request)

    # No brand answers for this host, so there is no site here to draw a page with.
    if page is None:
        return PlainTextResponse("not found", status_code=status_code)

    return render(page, template, status_code=status_code)


async def not_found(request: Request) -> Response | None:
    return await drawn(request, "pages/not-found.html", 404)


async def broke(request: Request) -> Response | None:
    return await drawn(request, "pages/error.html", 500)


async def get_private_page(page: Annotated[Page, Depends(get_page)]) -> Page:
    if page.user is None:
        raise SignInRequired()

    return page


def guard(page: Page, sent: str | None) -> None:
    """Every form of the site proves it was drawn by this site, because a post from anywhere else is one nobody meant to send."""
    if not csrf.valid(page.request, sent):
        raise PageExpired()


async def refused_by_captcha(page: Page, answer: str | None, token: str | None) -> dict:
    """What the form draws next to the challenge when it was not answered, because a page of the site never leaves as JSON."""
    if await captcha.verify(answer, token, page.request.client.host if page.request.client else None):
        return {}

    return {"captcha_answer": translate("error.captcha-invalid")}


CurrentPage = Annotated[Page, Depends(get_page)]
PrivatePage = Annotated[Page, Depends(get_private_page)]
CsrfToken = Annotated[str | None, Form(alias=csrf.FIELD)]
