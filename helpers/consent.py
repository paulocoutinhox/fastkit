"""What a visitor allowed a site to keep, which is asked once, answered freely, and changed as easily as it was given."""

from dataclasses import dataclass

from starlette.requests import Request
from starlette.responses import Response

from enums.consent import ConsentCategory
from helpers import cookies
from helpers.settings import settings
from helpers.signing import sign, unsign


@dataclass(frozen=True)
class Consent:
    """The answer a browser carries, where nothing beyond the necessary is allowed until somebody says so."""

    allowed: frozenset[ConsentCategory] = frozenset()
    answered: bool = False

    def __contains__(self, category: str) -> bool:
        return ConsentCategory(category) == ConsentCategory.NECESSARY or ConsentCategory(category) in self.allowed


def given(request: Request) -> Consent:
    """The answer this browser carries, which is no answer at all when the question has changed since it was given."""
    payload = unsign("consent", request.cookies.get(settings.site.consent.cookie))

    # An answer given about another version of the question is not an answer to this one.
    if not payload or payload.get("version") != settings.site.consent.version:
        return Consent()

    # The answer is read against what is offered today, so a category this instance dropped stops being allowed by an old cookie.
    named = set(payload.get("allowed", []))

    return Consent(allowed=frozenset(category for category in settings.site.consent.optional if str(category) in named), answered=True)


def remember(response: Response, allowed: set[ConsentCategory]) -> None:
    """The answer is written where the browser keeps it, and it is the record that the question was asked."""
    payload = {"version": settings.site.consent.version, "allowed": sorted(str(category) for category in allowed)}

    cookies.remember(response, settings.site.consent.cookie, sign("consent", payload, settings.site.consent.max_age), settings.site.consent.max_age)


def wanted(form, action: str) -> set[ConsentCategory]:
    """What the buttons and the boxes of the page add up to, where refusing everything is one click exactly like allowing it."""
    offered = set(settings.site.consent.optional)

    if action == "accept":
        return offered

    if action == "reject":
        return set()

    return {category for category in offered if form.get(str(category))}
