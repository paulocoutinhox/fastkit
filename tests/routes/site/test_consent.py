"""Nothing beyond what the site needs is kept until a visitor says so, and withdrawing is as easy as giving."""

import pytest

from enums.banner import BannerPlacement
from enums.consent import ConsentCategory
from helpers.consent import Consent, given, wanted
from helpers.settings import settings
from tests.conftest import opened
from tests.factories import make_banner


def answer_of(response):
    return response.cookies.get(settings.site.consent.cookie)


async def test_a_visitor_who_was_never_asked_reads_the_notice(site):
    answer = await site.get("/")

    assert "data-consent" in answer.text
    assert 'action="/cookies"' in answer.text


async def test_refusing_everything_is_one_click_exactly_like_allowing_it(site):
    """A page where saying no takes more work than saying yes is not a page that asked."""
    body = (await site.get("/")).text
    banner = body[body.index("data-consent") : body.index("</form>", body.index("data-consent"))]

    assert banner.count('type="submit"') == 2
    assert banner.count('value="reject"') == 1
    assert banner.count('value="accept"') == 1


async def test_the_notice_is_gone_once_the_question_was_answered(site):
    token = await opened(site, "/")
    await site.post("/cookies", data={"csrf_token": token, "action": "reject", "next": "/"})

    assert "data-consent" not in (await site.get("/")).text


async def test_allowing_everything_allows_everything_that_is_offered(site):
    token = await opened(site, "/")
    await site.post("/cookies", data={"csrf_token": token, "action": "accept", "next": "/"})

    page = await site.get("/cookies")

    for category in settings.site.consent.optional:
        assert f'name="{category}" checked' in page.text


async def test_refusing_leaves_nothing_but_the_necessary_allowed(site):
    token = await opened(site, "/")
    await site.post("/cookies", data={"csrf_token": token, "action": "reject", "next": "/"})

    page = await site.get("/cookies")

    assert "checked" in page.text
    assert page.text.count("checked") == 1


async def test_a_category_is_allowed_one_at_a_time(site):
    token = await opened(site, "/cookies")
    await site.post("/cookies", data={"csrf_token": token, "action": "save", "analytics": "on", "next": "/cookies"})

    page = await site.get("/cookies")

    assert 'name="analytics" checked' in page.text
    assert 'name="marketing" checked' not in page.text


async def test_the_answer_goes_back_to_the_page_it_was_given_from(site):
    token = await opened(site, "/plans")
    answer = await site.post("/cookies", data={"csrf_token": token, "action": "accept", "next": "/plans"}, follow_redirects=False)

    assert answer.status_code == 303
    assert answer.headers["location"] == "/plans"


async def test_the_answer_is_never_a_way_to_send_somebody_off_this_site(site):
    token = await opened(site, "/")
    answer = await site.post("/cookies", data={"csrf_token": token, "action": "accept", "next": "//evil.test/steal"}, follow_redirects=False)

    assert answer.headers["location"] == "/"


async def test_an_answer_with_no_token_is_not_an_answer(site):
    answer = await site.post("/cookies", data={"action": "accept", "next": "/"}, follow_redirects=False)

    assert answer.status_code == 303
    assert answer_of(answer) is None


async def test_the_page_that_asks_is_reachable_from_every_page(site):
    assert 'href="/cookies"' in (await site.get("/plans")).text


async def test_the_page_that_asks_says_where_the_policy_is(site, db, tenant):
    """It points at the policy where somebody wrote one, and at nothing at all where nobody did."""
    from tests.factories import make_content

    assert 'href="/content/cookies"' not in (await site.get("/cookies")).text

    await make_content(db, tenant, tag="cookies", title="Cookies")
    await db.commit()

    assert 'href="/content/cookies"' in (await site.get("/cookies")).text


def test_a_browser_carrying_no_answer_has_not_answered():
    consent = Consent()

    assert consent.answered is False
    assert ConsentCategory.NECESSARY in consent
    assert ConsentCategory.ANALYTICS not in consent


def test_what_the_site_cannot_answer_without_is_never_asked_about():
    assert ConsentCategory.NECESSARY not in settings.site.consent.optional
    assert ConsentCategory.NECESSARY in Consent(allowed=frozenset(), answered=True)


@pytest.mark.parametrize("action, expected", [("accept", 3), ("reject", 0), ("save", 1)])
def test_the_buttons_and_the_boxes_add_up_to_what_was_allowed(action, expected):
    assert len(wanted({"analytics": "on"}, action)) == expected


async def test_an_answer_given_about_another_question_is_no_answer_to_this_one(site, monkeypatch):
    """Asking for something new is asking again, and a cookie written before it cannot speak for it."""
    token = await opened(site, "/")
    await site.post("/cookies", data={"csrf_token": token, "action": "accept", "next": "/"})

    monkeypatch.setattr(settings.site.consent, "version", settings.site.consent.version + 1)

    assert "data-consent" in (await site.get("/")).text


async def test_a_category_this_instance_stopped_asking_about_stops_being_allowed(site, monkeypatch):
    token = await opened(site, "/")
    await site.post("/cookies", data={"csrf_token": token, "action": "accept", "next": "/"})

    monkeypatch.setattr(settings.site.consent, "optional", [ConsentCategory.PREFERENCES])

    page = await site.get("/cookies")

    assert 'name="preferences" checked' in page.text
    assert 'name="analytics"' not in page.text


def test_a_cookie_nobody_wrote_is_read_as_nobody_having_answered():
    class Bare:
        cookies = {}

    assert given(Bare()).answered is False


async def test_the_language_a_visitor_chose_outlives_the_visit_only_where_it_was_allowed(site):
    """A cookie of preference is one somebody allowed, and the choice still holds for the visit either way."""
    token = await opened(site, "/plans")
    await site.post("/cookies", data={"csrf_token": token, "action": "reject", "next": "/plans"})

    token = await opened(site, "/plans")
    chosen = await site.post("/language", data={"csrf_token": token, "language": "pt", "next": "/plans"}, follow_redirects=False)
    written = chosen.headers["set-cookie"]

    assert "fastkit_language=pt" in written
    assert "Max-Age" not in written


async def test_allowing_preferences_is_what_makes_the_choice_last(site):
    token = await opened(site, "/plans")
    await site.post("/cookies", data={"csrf_token": token, "action": "accept", "next": "/plans"})

    token = await opened(site, "/plans")
    chosen = await site.post("/language", data={"csrf_token": token, "language": "pt", "next": "/plans"}, follow_redirects=False)

    assert f"Max-Age={settings.site.language_max_age}" in chosen.headers["set-cookie"]


def written_for(answer, cookie: str) -> str:
    return next(line for line in answer.headers.get_list("set-cookie") if line.startswith(f"{cookie}="))


@pytest.mark.parametrize("cookie", ["fastkit_language", "fastkit_theme"])
async def test_the_answer_decides_how_long_every_preference_already_chosen_lives(site, cookie):
    """A palette is a preference exactly as a language is, so an answer that rewrites one and forgets the other keeps what nobody allowed and drops what somebody did."""
    token = await opened(site, "/plans")

    await site.post("/language", data={"csrf_token": token, "language": "pt", "next": "/plans"})
    await site.post("/theme", data={"csrf_token": token, "theme": "dark", "next": "/plans"})

    token = await opened(site, "/plans")
    allowed = await site.post("/cookies", data={"csrf_token": token, "action": "accept", "next": "/plans"}, follow_redirects=False)

    assert "Max-Age" in written_for(allowed, cookie), f"{cookie} was chosen and allowing preferences left it to the visit"

    token = await opened(site, "/plans")
    withdrawn = await site.post("/cookies", data={"csrf_token": token, "action": "reject", "next": "/plans"}, follow_redirects=False)

    assert "Max-Age" not in written_for(withdrawn, cookie), f"{cookie} outlives an answer that withdrew it"


async def test_the_name_a_reader_is_counted_by_is_written_only_where_analytics_was_allowed(site):
    token = await opened(site, "/cookies")

    await site.post("/cookies", data={"csrf_token": token, "action": "accept", "next": "/"})

    assert site.cookies.get(settings.site.visitor_cookie) is not None


async def test_answering_the_same_consent_question_again_does_not_turn_one_reader_into_another(site):
    token = await opened(site, "/cookies")
    await site.post("/cookies", data={"csrf_token": token, "action": "accept", "next": "/"})
    first = site.cookies.get(settings.site.visitor_cookie)

    token = await opened(site, "/cookies")
    await site.post("/cookies", data={"csrf_token": token, "action": "accept", "next": "/"})

    assert site.cookies.get(settings.site.visitor_cookie) == first


async def test_refusing_leaves_nobody_to_count(site):
    token = await opened(site, "/cookies")

    await site.post("/cookies", data={"csrf_token": token, "action": "reject", "next": "/"})

    assert site.cookies.get(settings.site.visitor_cookie) is None


async def test_withdrawing_takes_the_name_away_instead_of_keeping_it_unused(site):
    token = await opened(site, "/cookies")
    await site.post("/cookies", data={"csrf_token": token, "action": "accept", "next": "/"})

    assert site.cookies.get(settings.site.visitor_cookie) is not None

    token = await opened(site, "/cookies")
    await site.post("/cookies", data={"csrf_token": token, "action": "reject", "next": "/"})

    # Counting a reader is what the category names, so taking it back is what stops the counting.
    assert site.cookies.get(settings.site.visitor_cookie) is None


async def test_a_banner_is_not_counted_for_a_reader_who_never_allowed_it(site, db, tenant, tenant_headers):
    banner = await make_banner(db, tenant)

    answer = await site.post(f"/api/banners/{banner.uuid}/view", json={}, headers=tenant_headers)

    await db.refresh(banner)

    assert answer.status_code == 204
    assert banner.views == 0


async def test_a_banner_is_counted_for_a_reader_who_allowed_it(site, db, tenant, tenant_headers):
    banner = await make_banner(db, tenant)
    token = await opened(site, "/cookies")

    await site.post("/cookies", data={"csrf_token": token, "action": "accept", "next": "/"})
    answer = await site.post(f"/api/banners/{banner.uuid}/view", json={}, headers=tenant_headers)

    await db.refresh(banner)

    # The cookie the page cannot read is what names the reader, so the browser sends it and the body carries nothing.
    assert answer.status_code == 204
    assert banner.views == 1


async def test_a_banner_is_marked_countable_only_where_counting_is_allowed(site, db, tenant):
    """The server counts nobody who did not allow analytics, so asking it to is two calls a page that answer nothing and spend a rate limit."""
    await make_banner(db, tenant, title="Welcome", placement=BannerPlacement.HOME)

    assert "data-banner" not in (await site.get("/")).text, "a reader who answered nothing is asked to be counted"

    await site.post("/cookies", data={"csrf_token": await opened(site, "/cookies"), "action": "reject"}, follow_redirects=False)

    assert "data-banner" not in (await site.get("/")).text, "a reader who refused keeps being asked to be counted"

    await site.post("/cookies", data={"csrf_token": await opened(site, "/cookies"), "action": "accept"}, follow_redirects=False)

    assert "data-banner" in (await site.get("/")).text, "a reader who allowed it is never counted at all"
