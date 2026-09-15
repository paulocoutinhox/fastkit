"""Everything a page of the site is built out of, settled once per request."""

import json
import logging
import re
from dataclasses import dataclass, field
from functools import partial
from urllib.parse import quote, urlparse

import jwt
from fastapi import FastAPI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from starlette.requests import Request
from starlette.responses import HTMLResponse, PlainTextResponse, RedirectResponse, Response

from enums.consent import ConsentCategory
from enums.theme import Theme
from enums.user import UserStatus
from helpers import brand, cookies, csrf
from helpers.brand import Brand
from helpers.consent import Consent
from helpers.dates import read_in
from helpers.db import AsyncSessionLocal
from helpers.i18n import current_locale, resolve_locale, translate
from helpers.security import decode_token
from helpers.settings import settings
from helpers.signing import sign, unsign
from helpers.templates import render as render_template
from models.base import BIG_INTEGER_MAX
from models.tenant import Tenant
from models.user import User

FLASH_TTL = 60

# The pages the navigation names, and the address each of them opens, because every page of the site draws these links.
NAVIGATION = {"about": "/about", "terms": "/content/terms", "privacy": "/content/privacy", "cookies": "/content/cookies"}

# A page past this asks for an offset no column holds, and the number would overflow inside the driver instead of answering.
LAST_PAGE = BIG_INTEGER_MAX // settings.site.page_size

logger = logging.getLogger(__name__)


class PageNotFound(Exception):
    """A path of the site that names nothing, which is a page with a status and never a JSON body."""


class SignInRequired(Exception):
    """A page of the account reached by somebody with no session, which is a redirect and never an error page."""


class PageExpired(Exception):
    """A form whose page went stale, which is the page drawn again with a notice and never a body of JSON."""


@dataclass
class Page:
    """What every template of the site is rendered with, built once per request."""

    request: Request
    brand: Brand
    language: str
    user: User | None = None
    flashes: list[dict] = field(default_factory=list)
    csrf_token: str = ""
    consent: Consent = field(default_factory=Consent)
    theme: Theme = Theme.SYSTEM
    pages: frozenset[str] = frozenset()

    @property
    def counts(self) -> bool:
        """Whether what this reader does is counted at all, which nobody is until they allowed analytics to be kept."""
        return ConsentCategory.ANALYTICS in self.consent

    @property
    def zone(self) -> str:
        """The clock this page is read by, which is the one the account keeps and UTC for a reader who has none."""
        return self.user.timezone if self.user else "UTC"

    def url(self, path: str = "") -> str:
        """An address of the site carries no language, so the same page is one address in every language a person reads it in."""
        return path or "/"

    @property
    def canonical(self) -> str:
        """The one address this page is, which is neither the one somebody arrived at nor the host they named: a tracking parameter and a stray host would each make a page of their own to a crawler."""
        return self.brand.address(self.request.url.path)

    def at(self, path: str) -> bool:
        """Whether this page is the one that address opens or a page below it, which is what marks a menu item as where the reader is."""
        here = self.request.url.path.rstrip("/") or "/"
        section = path.rstrip("/") or "/"

        # The home is every page of the site by that rule, so it is the one address that only marks itself.
        if section == "/":
            return here == "/"

        return here == section or here.startswith(f"{section}/")


def owned_elsewhere_path(path: str) -> bool:
    """Whether a path belongs to the API or to the admin, compared exactly: `/administrators` is not the admin."""
    owners = (settings.api_path, settings.admin_path)

    return any(path == owner or path.startswith(f"{owner}/") for owner in owners)


def owned_elsewhere(request: Request) -> bool:
    """The API and the admin own their paths, so a page never answers for one of them however wide the site route is."""
    return owned_elsewhere_path(request.url.path)


def host_of(request: Request) -> str:
    return (request.headers.get("host") or "").split(":")[0].lower()


async def brand_of(db: AsyncSession, request: Request) -> Brand | None:
    """Whose site this is, which the host says where this instance serves many brands and the configuration says where it serves one."""
    if not settings.multi_tenant:
        return brand.of(None)

    host = host_of(request)
    found = await db.scalar(select(Tenant).where(Tenant.domain == host, Tenant.active.is_(True)))

    if found is None and settings.site.default_tenant:
        found = await db.scalar(select(Tenant).where(Tenant.code == settings.site.default_tenant, Tenant.active.is_(True)))

    if found is None:
        # Every page of this instance is dark in this state, and the answer stays quiet so nobody outside learns how it is configured.
        logger.warning("[site] no active brand answers for %s, and the default is %s", host, settings.site.default_tenant or "not set")

        return None

    return brand.of(found)


def chosen_language(request: Request, user: User | None) -> str:
    """What the person reading this page chose, where the account outranks the cookie and the cookie outranks the browser."""
    if user is not None and user.language is not None and user.language.code_iso_639_1 in settings.languages:
        return user.language.code_iso_639_1

    stored = request.cookies.get(settings.site.language_cookie)

    if stored in settings.languages:
        return stored

    return resolve_locale(request.headers.get("accept-language"))


async def account_of(db: AsyncSession, request: Request) -> User | None:
    """The session of the site is the same token the API mints, kept in a cookie the page never reads."""
    token = request.cookies.get(settings.site.session_cookie)

    if not token:
        return None

    try:
        claims = decode_token(token)
    except jwt.PyJWTError:
        return None

    user = await db.scalar(select(User).options(selectinload(User.language)).where(User.token == claims["sub"]))

    if user is None or user.status != UserStatus.ACTIVE or claims.get("epoch") != user.session_epoch:
        return None

    return user


def taken(request: Request) -> list[dict]:
    """A flash is read once, so what is on the request now is what the last response left there."""
    raw = request.cookies.get(settings.site.flash_cookie)

    if not raw:
        return []

    payload = unsign("flash", raw)

    return payload["messages"] if payload else []


def flash(response: Response, messages: list[dict]) -> None:
    cookies.remember(response, settings.site.flash_cookie, sign("flash", {"messages": messages}, FLASH_TTL))


def clear_flash(response: Response) -> None:
    cookies.forget(response, settings.site.flash_cookie)


@dataclass(frozen=True)
class Paging:
    """What a listing of the site draws under itself, counted in pages because a page is what a person clicks."""

    page: int
    limit: int
    total: int = 0

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.limit

    @property
    def pages(self) -> int:
        return max(1, -(-self.total // self.limit))

    def of(self, total: int) -> "Paging":
        """The same request once the listing has been counted, which is what the template needs to draw the last page number."""
        return Paging(page=self.page, limit=self.limit, total=total)


def page_number(asked: str) -> int:
    """The page that was asked for, where anything a page number cannot be is the first one."""
    # A run of digits longer than the last page is read before it is converted, because past a few thousand of them the conversion is what raises.
    if not asked.isdigit() or len(asked) > len(str(LAST_PAGE)):
        return 1

    wanted = int(asked)

    return wanted if 0 < wanted <= LAST_PAGE else 1


def paged(request: Request) -> Paging:
    """The page a visitor asked for, which is the first one whenever the query says something a page number cannot be."""
    return Paging(page=page_number(request.query_params.get("page", "1")), limit=settings.site.page_size)


# What a browser drops before it reads an address, and the separator it reads as a slash.
STRIPPED = re.compile(r"[\x00-\x20\x7f\\]")


def inside(path: str, default: str = "/") -> str:
    """Where a page says to go next, which is a page of this site however the value arrived."""
    # The characters go first because a browser drops them first, and `/\evil.test` is another host to one.
    wanted = STRIPPED.sub("", path or "")

    if not wanted.startswith("/") or wanted.startswith("//"):
        return default

    # The site never hands somebody to the API or to the panel, whatever the field says.
    if owned_elsewhere_path(wanted.split("?")[0]):
        return default

    return wanted


# One button carries the whole choice, so it names where the next press lands.
NEXT_THEME = {Theme.SYSTEM: Theme.LIGHT, Theme.LIGHT: Theme.DARK, Theme.DARK: Theme.SYSTEM}

# What the stylesheet calls each palette, because a person chooses light or dark and the theme that draws the dark one is named after the colour it is.
DRAWN_AS = {Theme.LIGHT: "light", Theme.DARK: "black"}


def chosen_theme(request: Request) -> Theme:
    """The palette this browser asked for, which is the one the device already uses until somebody says otherwise."""
    written = request.cookies.get(settings.site.theme_cookie, "")

    return Theme(written) if written in set(Theme) else Theme.SYSTEM


def remember_theme(response: Response, theme: Theme, consent: Consent) -> None:
    """A palette is a preference like the language, so it outlives the visit only where somebody allowed it to."""
    remembered = settings.site.theme_max_age if ConsentCategory.PREFERENCES in consent else None

    cookies.remember(response, settings.site.theme_cookie, theme.value, remembered)


def remember_language(response: Response, language: str, consent: Consent) -> None:
    """The choice of somebody with no account lives here, and how long it lives is what the visitor allowed."""
    # A cookie of preference outlives the visit only where somebody said it could, and the choice still holds for this one either way.
    remembered = settings.site.language_max_age if ConsentCategory.PREFERENCES in consent else None

    cookies.remember(response, settings.site.language_cookie, language, remembered)


def sign_in(response: Response, token: str) -> None:
    cookies.remember(response, settings.site.session_cookie, token, settings.site.cookie_max_age)


def sign_out(response: Response) -> None:
    cookies.forget(response, settings.site.session_cookie)


def asset(name: str) -> str:
    """The build writes fixed names, so what tells a browser the file changed is the moment the build wrote it."""
    written = settings.site.assets / name

    return f"{settings.site.assets_url}/{name}?v={int(written.stat().st_mtime) if written.is_file() else settings.version}"


def assets() -> dict:
    """Read on every page rather than once, because a build that runs while the server is up has to reach the next reload."""
    return {"styles_url": asset("styles.css"), "scripts_url": asset("scripts.js"), "favicon_url": asset("favicon.svg")}


def offered_categories() -> list[dict]:
    """What the consent page draws a row for, named and explained here so no template ever spells a key it built."""
    return [{"name": str(category), "label": translate(f"site.cookies-{category}"), "lead": translate(f"site.cookies-{category}-lead")} for category in settings.site.consent.optional]


def context_of(page: Page, extra: dict | None = None) -> dict:
    return {
        "page": page,
        "request": page.request,
        "brand": page.brand,
        "user": page.user,
        "language": page.language,
        "languages": settings.languages,
        "flashes": page.flashes,
        "csrf_field": csrf.FIELD,
        "csrf_token": page.csrf_token,
        "consent": page.consent,
        "consent_categories": offered_categories(),
        "theme": page.theme,
        "navigation": {tag: address for tag, address in NAVIGATION.items() if tag in page.pages},
        "theme_drawn_as": DRAWN_AS.get(page.theme, ""),
        "day": partial(read_in, zone=page.zone, shape="%Y-%m-%d"),
        "moment": partial(read_in, zone=page.zone, shape="%Y-%m-%d %H:%M"),
        "next_theme": NEXT_THEME[page.theme],
        **assets(),
        "url": page.url,
        "canonical": page.canonical,
        "version": settings.version,
        **(extra or {}),
    }


def render(page: Page, template: str, extra: dict | None = None, status_code: int = 200) -> HTMLResponse:
    """Every page of the site leaves through here, so the session cookie of the form and the flash are settled in one place."""
    body = render_template(f"site/{template}", page.brand.code, context_of(page, extra))
    response = HTMLResponse(body, status_code=status_code)

    csrf.remember(response, page.csrf_token)

    if page.flashes:
        clear_flash(response)

    return response


def redirect(page: Page, path: str, messages: list[dict] | None = None) -> RedirectResponse:
    """A write answers a redirect, so a reload never sends the same form twice."""
    response = RedirectResponse(page.url(path), status_code=303)

    if messages:
        flash(response, messages)

    return response


def notice(key: str, level: str = "success", **params) -> dict:
    return {"level": level, "message": translate(key, **params)}


def setup(app: FastAPI) -> None:
    @app.exception_handler(PageExpired)
    async def handle_page_expired(request: Request, exc: PageExpired):
        """The form is sent back to the page it was drawn on, where a token this site issued is waiting for it."""
        came_from = urlparse(request.headers.get("referer") or "").path or "/"
        answer = RedirectResponse(inside(came_from), status_code=303)

        flash(answer, [notice("error.csrf-invalid", "error")])

        return answer

    @app.exception_handler(SignInRequired)
    async def handle_sign_in_required(request: Request, exc: SignInRequired):
        """Where somebody was going is carried to the sign in, and coming back is always a GET, so a form names the page it was drawn on."""
        if request.method == "GET":
            wanted = request.url.path + (f"?{request.url.query}" if request.url.query else "")
        else:
            wanted = urlparse(request.headers.get("referer") or "").path or "/"

        return RedirectResponse(f"/account/login?next={quote(inside(wanted), safe='')}", status_code=303)

    @app.exception_handler(PageNotFound)
    async def handle_page_not_found(request: Request, exc: PageNotFound):
        return await not_found(request)


async def drawn(request: Request, template: str, status_code: int) -> Response | None:
    """A page of the site the visitor lands on instead of a body written for a client, and nothing at all where the address belongs elsewhere."""
    if owned_elsewhere(request):
        return None

    async with AsyncSessionLocal() as session:
        found = await brand_of(session, request)
        user = await account_of(session, request)

    # No brand answers for this host, so there is no site here to draw a page with.
    if found is None:
        return PlainTextResponse("not found", status_code=status_code)

    language = chosen_language(request, user)
    current_locale.set(language)

    return render(Page(request=request, brand=found, language=language, user=user, csrf_token=csrf.issue(request), theme=chosen_theme(request)), template, status_code=status_code)


async def not_found(request: Request) -> Response | None:
    return await drawn(request, "pages/not-found.html", 404)


async def broke(request: Request) -> Response | None:
    return await drawn(request, "pages/error.html", 500)


def structured_data(brand: Brand) -> str:
    """What a search engine reads to know whose site this is, written once and rendered into the head."""
    body = json.dumps({"@context": "https://schema.org", "@type": "Organization", "name": brand.name, "url": brand.address("/")}, ensure_ascii=False)

    # This is written into a script block, and a name carrying `</script>` would close it and turn the rest of the page into markup.
    return body.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
