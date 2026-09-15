from typing import Annotated

from fastapi import Depends, Form, Request

from helpers import cache, captcha, consent, csrf
from helpers.db import DatabaseSession
from helpers.i18n import current_locale, translate
from helpers.site import NAVIGATION, Page, PageExpired, PageNotFound, SignInRequired, account_of, brand_of, chosen_language, chosen_theme, taken
from services.content import content_service


async def get_page(request: Request, db: DatabaseSession) -> Page:
    """The one place a page of the site is built, so the brand, the language and the session are settled once."""
    brand = await brand_of(db, request)

    if brand is None:
        raise PageNotFound()

    user = await account_of(db, request)
    language = chosen_language(request, user)

    # An address of the site says nothing about language, so what the person chose is what the page is rendered in.
    current_locale.set(language)

    async def answered():
        return sorted(await content_service.tags_that_answer(db, tuple(NAVIGATION), brand.id, language))

    drawn = await cache.answered(cache.content, cache.named(surface="navigation", tenant=brand.id, language=language), answered)

    return Page(request=request, brand=brand, language=language, user=user, flashes=taken(request), csrf_token=csrf.issue(request), consent=consent.given(request), theme=chosen_theme(request), pages=frozenset(drawn))


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
