from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from config.base import BASE_DIR, SLUG
from config.consent_settings import ConsentSettings


class SiteSettings(BaseModel):
    """The public site, which is rendered by this process and carries a session of its own."""

    assets: Path = BASE_DIR / "webapps" / "site" / "dist"
    assets_url: str = "/static"

    # The tenant this instance serves when the host names none, which a machine with no domain of its own needs.
    default_tenant: str = ""

    # Where this instance answers, which a message written by a cron cannot read off a request that does not exist.
    domain: str = "change-me"

    # How many rows a listing of the site draws before it asks the visitor to turn the page.
    page_size: int = 20

    session_cookie: str = f"{SLUG}_session"
    authentication_cookie_prefix: str = f"{SLUG}-sign-in"
    flash_cookie: str = f"{SLUG}_flash"

    # What proves a form was drawn here, named beside the other six so that no cookie of this site is spelled anywhere else.
    csrf_cookie: str = f"{SLUG}_csrf"

    # The language a visitor chose, which is where it lives for somebody with no account to keep it in.
    language_cookie: str = f"{SLUG}_language"

    # The palette a visitor chose, kept the same way and for the same reason as the language.
    theme_cookie: str = f"{SLUG}_theme"

    # The name a reader is counted by, which is kept only where somebody allowed analytics to be kept.
    visitor_cookie: str = f"{SLUG}_visitor"
    visitor_max_age: int = 60 * 60 * 24 * 365

    consent: ConsentSettings = Field(default_factory=ConsentSettings)

    # How this environment addresses itself, which a message written by a cron cannot read off a request.
    scheme: Literal["http", "https"] = "https"

    # A cookie of a session travels over https, and the machine of whoever develops is the one that says it has none.
    cookie_secure: bool = True

    # How long a browser is told never to speak http with this host again, where zero is an installation saying not to tell it.
    hsts_max_age: int = 60 * 60 * 24 * 365
    cookie_max_age: int = 60 * 60 * 24 * 30
    csrf_ttl: int = 3600
