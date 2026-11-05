"""What every template of the site is rendered with, built once per request."""

from dataclasses import dataclass
from urllib.parse import urlparse

from starlette.requests import Request

from enums.consent_category import ConsentCategory
from enums.theme import Theme
from helpers.brand import Brand
from helpers.consent import Consent
from helpers.text import falls_under
from models.user import User


@dataclass
class Page:
    request: Request
    brand: Brand
    language: str
    user: User | None
    flashes: list[dict]
    csrf_token: str
    consent: Consent
    theme: Theme
    pages: frozenset[str]

    @property
    def counts(self) -> bool:
        """Whether what this reader does is counted at all, which nobody is until they allowed analytics to be kept."""
        return ConsentCategory.ANALYTICS in self.consent

    @property
    def zone(self) -> str:
        """The clock this page is read by, which is the one the account keeps and UTC for a reader who has none."""
        return self.user.timezone if self.user else "UTC"

    @property
    def here(self) -> str:
        """Coming back is always a GET, so a page drawn again after a refused form is the page that form was drawn on, with the query it carried."""
        return address_of(self.request.url) if self.request.method == "GET" else came_from(self.request)

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

        return falls_under(here, section)


def address_of(url) -> str:
    """The path with the query it carried, so going back somewhere keeps the page of a listing and the destination a sign in was holding."""
    return url.path + (f"?{url.query}" if url.query else "")


def came_from(request: Request) -> str:
    """The page a form was drawn on, read from a header the client writes, so one that names no address is the home, like one that is not there."""
    try:
        return address_of(urlparse(request.headers.get("referer") or "")) or "/"
    except ValueError:
        return "/"
