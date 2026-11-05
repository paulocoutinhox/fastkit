from urllib.parse import parse_qs, urlsplit

import pytest
from sqlalchemy import func, select

from enums.social_provider import SocialProvider
from helpers.authentication_cookie_helper import AuthenticationCookieHelper
from helpers.settings import settings
from models.login_ticket import LoginTicket
from models.outbound_email import OutboundEmail
from models.social_identity import SocialIdentity
from models.social_login_attempt import SocialLoginAttempt
from models.user import User
from tests.conftest import opened, token_in
from tests.factories import save
from tests.helpers.social_login_test_helper import SocialLoginTestHelper


@pytest.mark.parametrize("path", ["/account/email-login", "/account/email-login/confirm", "/account/social/google/start"])
async def test_disabled_optional_sign_in_pages_answer_the_sites_not_found_page(site, path):
    answer = await site.get(path)

    assert answer.status_code == 404
    assert "text/html" in answer.headers["content-type"]


async def test_optional_sign_in_controls_are_not_advertised_by_default(site):
    answer = await site.get("/account/login")

    assert "/account/email-login" not in answer.text
    assert "/account/social/google/start" not in answer.text


async def test_the_site_creates_an_account_only_after_the_email_code_is_confirmed(site, db, tenant, email_login):
    csrf = await opened(site, "/account/email-login?next=/account/profile")
    requested = await site.post("/account/email-login", data={"csrf_token": csrf, "email": "new@example.com", "next": "/account/profile"}, follow_redirects=False)

    assert requested.status_code == 303
    assert await db.scalar(select(func.count()).select_from(User)) == 0

    query = parse_qs(urlsplit(requested.headers["location"]).query)
    form = await site.get(requested.headers["location"])
    message = await db.scalar(select(OutboundEmail))
    answer = await site.post("/account/email-login/confirm", data={"csrf_token": token_in(form.text), "challenge": query["challenge"][0], "code": message.context["code"], "next": "/account/profile"}, follow_redirects=False)

    assert answer.status_code == 303
    assert answer.headers["location"] == "/account/profile"
    assert site.cookies.get(settings.site.session_cookie)
    assert (await site.get("/account")).status_code == 200
    assert (await db.scalar(select(User))).first_name is None


async def test_email_sign_in_forms_require_csrf_and_validate_email_addresses(site, db, email_login):
    answer = await site.post("/account/email-login", data={"email": "new@example.com"}, follow_redirects=False)

    assert answer.status_code == 303
    assert await db.scalar(select(func.count()).select_from(OutboundEmail)) == 0

    csrf = await opened(site, "/account/email-login")
    answer = await site.post("/account/email-login", data={"csrf_token": csrf, "email": "invalid"})

    assert answer.status_code == 422
    assert "text/html" in answer.headers["content-type"]


async def test_a_wrong_email_code_redraws_the_form_without_starting_a_session(site, db, email_login):
    csrf = await opened(site, "/account/email-login")
    requested = await site.post("/account/email-login", data={"csrf_token": csrf, "email": "new@example.com"}, follow_redirects=False)
    form = await site.get(requested.headers["location"])
    token = parse_qs(urlsplit(requested.headers["location"]).query)["challenge"][0]
    message = await db.scalar(select(OutboundEmail))
    wrong = "111111" if message.context["code"] != "111111" else "222222"

    answer = await site.post("/account/email-login/confirm", data={"csrf_token": token_in(form.text), "challenge": token, "code": wrong})

    assert answer.status_code == 422
    assert "incorrect" in answer.text
    assert site.cookies.get(settings.site.session_cookie) is None


async def test_the_site_handles_the_full_social_callback_and_keeps_the_token_out_of_the_url(site, db, social_login, social_keys, monkeypatch):
    start = await site.get("/account/social/google/start?next=/account/profile", follow_redirects=False)
    state = parse_qs(urlsplit(start.headers["location"]).query)["state"][0]
    attempt = await db.scalar(select(SocialLoginAttempt))
    SocialLoginTestHelper.answer_provider(monkeypatch, SocialProvider.GOOGLE, social_login[SocialProvider.GOOGLE], attempt, social_keys)

    answer = await site.get(f"/account/social/google/callback?state={state}&code=authorization-code", follow_redirects=False)

    assert answer.status_code == 303
    assert answer.headers["location"] == "/account/profile"
    assert site.cookies.get(settings.site.session_cookie)
    assert not site.cookies.get(AuthenticationCookieHelper.name(state))
    assert (await site.get("/account/profile")).status_code == 200


async def test_the_admin_callback_uses_a_single_use_ticket_instead_of_a_site_session(site, db, tenant, administrator, social_login, social_keys, monkeypatch):
    await save(db, SocialIdentity(user_id=administrator.id, tenant_id=None, provider=SocialProvider.GOOGLE, subject="provider-account"))
    start = await site.get("/account/social/google/start?surface=admin&next=/profile", follow_redirects=False)
    state = parse_qs(urlsplit(start.headers["location"]).query)["state"][0]
    attempt = await db.scalar(select(SocialLoginAttempt))
    SocialLoginTestHelper.answer_provider(monkeypatch, SocialProvider.GOOGLE, social_login[SocialProvider.GOOGLE], attempt, social_keys)

    answer = await site.get(f"/account/social/google/callback?state={state}&code=authorization-code", follow_redirects=False)
    destination = urlsplit(answer.headers["location"])
    ticket = parse_qs(destination.fragment)["sign-in"][0]

    assert destination.path == "/admin/login"
    assert parse_qs(destination.query)["next"] == ["/profile"]
    assert not site.cookies.get(settings.site.session_cookie)
    assert (await db.scalar(select(LoginTicket))).consumed_at is None

    redeemed = await site.post("/api/admin/social/redeem", json={"ticket": ticket})

    assert redeemed.status_code == 200
    assert redeemed.json()["user"]["token"] == administrator.token
    assert site.cookies.get(AuthenticationCookieHelper.name(ticket)) is None


async def test_declining_social_consent_creates_no_account(site, db, social_login):
    start = await site.get("/account/social/google/start", follow_redirects=False)
    state = parse_qs(urlsplit(start.headers["location"]).query)["state"][0]

    answer = await site.get(f"/account/social/google/callback?state={state}&error=access_denied", follow_redirects=False)

    assert answer.headers["location"] == "/account/login"
    assert "cancelled" in (await site.get("/account/login")).text
    assert await db.scalar(select(func.count()).select_from(User)) == 0


async def test_a_callback_from_another_browser_is_refused(site, social_login):
    start = await site.get("/account/social/google/start", follow_redirects=False)
    state = parse_qs(urlsplit(start.headers["location"]).query)["state"][0]
    site.cookies.delete(AuthenticationCookieHelper.name(state))

    answer = await site.get(f"/account/social/google/callback?state={state}&code=authorization-code")

    assert answer.status_code == 400
    assert "invalid or expired" in answer.text


async def test_a_signed_in_person_can_connect_and_remove_a_social_account(signed_in, db, member, social_login, social_keys, monkeypatch):
    csrf = await opened(signed_in, "/account/connections")
    start = await signed_in.post("/account/connections/google/connect", data={"csrf_token": csrf}, follow_redirects=False)
    state = parse_qs(urlsplit(start.headers["location"]).query)["state"][0]
    attempt = await db.scalar(select(SocialLoginAttempt))
    SocialLoginTestHelper.answer_provider(monkeypatch, SocialProvider.GOOGLE, social_login[SocialProvider.GOOGLE], attempt, social_keys)

    answer = await signed_in.get(f"/account/social/google/callback?state={state}&code=authorization-code", follow_redirects=False)

    assert answer.headers["location"] == "/account/connections"
    assert (await db.scalar(select(SocialIdentity))).user_id == member.id

    csrf = await opened(signed_in, "/account/connections")
    removed = await signed_in.post("/account/connections/google/remove", data={"csrf_token": csrf}, follow_redirects=False)

    assert removed.status_code == 303
    assert await db.scalar(select(func.count()).select_from(SocialIdentity)) == 0


async def test_apple_uses_a_secure_cross_site_cookie_and_accepts_its_post_callback(site, db, social_login, social_keys, monkeypatch):
    site.base_url = f"https://{site.base_url.host}"
    start = await site.get("/account/social/apple/start", follow_redirects=False)
    state = parse_qs(urlsplit(start.headers["location"]).query)["state"][0]
    attempt = await db.scalar(select(SocialLoginAttempt))
    SocialLoginTestHelper.answer_provider(monkeypatch, SocialProvider.APPLE, social_login[SocialProvider.APPLE], attempt, social_keys)

    assert "SameSite=none" in start.headers["set-cookie"]
    assert "Secure" in start.headers["set-cookie"]
    assert "HttpOnly" in start.headers["set-cookie"]

    answer = await site.post("/account/social/apple/callback", data={"state": state, "code": "apple-code"}, follow_redirects=False)

    assert answer.status_code == 303
    assert site.cookies.get(settings.site.session_cookie)


async def test_other_social_providers_cannot_post_to_the_callback(site, social_login):
    answer = await site.post("/account/social/google/callback", data={"state": "a" * 43, "code": "code"})

    assert answer.status_code == 404


async def test_malformed_social_callback_fields_are_refused_as_an_html_page(site, social_login):
    answer = await site.get("/account/social/google/callback?state=invalid")

    assert answer.status_code == 400
    assert "text/html" in answer.headers["content-type"]


async def test_a_callback_without_an_authorization_code_does_not_open_a_session(site, social_login):
    start = await site.get("/account/social/google/start", follow_redirects=False)
    state = parse_qs(urlsplit(start.headers["location"]).query)["state"][0]

    answer = await site.get(f"/account/social/google/callback?state={state}", follow_redirects=False)

    assert answer.headers["location"] == "/account/login"
    assert not site.cookies.get(settings.site.session_cookie)


async def test_admin_social_errors_return_a_known_code_without_a_ticket(site, social_login):
    start = await site.get("/account/social/google/start?surface=admin", follow_redirects=False)
    state = parse_qs(urlsplit(start.headers["location"]).query)["state"][0]

    answer = await site.get(f"/account/social/google/callback?state={state}&error=access_denied", follow_redirects=False)

    assert answer.headers["location"] == "/admin/login#sign-in-error=error.social-denied"


async def test_an_operator_connecting_a_provider_returns_to_the_admin_profile_without_a_sign_in_ticket(site, db, administrator, admin_headers, social_login, social_keys, monkeypatch):
    start = await site.post("/api/account/social-connections/google/start", json={"surface": "admin"}, headers=admin_headers)
    state = parse_qs(urlsplit(start.json()["authorizationUrl"]).query)["state"][0]
    attempt = await db.scalar(select(SocialLoginAttempt))
    SocialLoginTestHelper.answer_provider(monkeypatch, SocialProvider.GOOGLE, social_login[SocialProvider.GOOGLE], attempt, social_keys)

    answer = await site.get(f"/account/social/google/callback?state={state}&code=authorization-code", follow_redirects=False)

    assert answer.headers["location"] == "/admin/profile"
    assert (await db.scalar(select(SocialIdentity))).user_id == administrator.id
    assert await db.scalar(select(func.count()).select_from(LoginTicket)) == 0


async def test_a_malformed_email_code_redraws_without_creating_an_account(site, db, email_login):
    csrf = await opened(site, "/account/email-login/confirm")
    answer = await site.post("/account/email-login/confirm", data={"csrf_token": csrf, "challenge": "malformed", "code": "123"})

    assert answer.status_code == 422
    assert await db.scalar(select(func.count()).select_from(User)) == 0


async def test_removing_the_only_social_method_keeps_the_connection_and_shows_its_reason(site, db, social_login):
    from helpers.security import create_token
    from services.social_login_service import social_login_service
    from services.social_profile import SocialProfile

    await site.get("/account/social/google/start", follow_redirects=False)
    attempt = await db.scalar(select(SocialLoginAttempt))
    user = await social_login_service.sign_in(db, attempt, SocialProfile("only-account"))
    site.cookies.set(settings.site.session_cookie, create_token(user.token, user.role, user.session_epoch))
    csrf = await opened(site, "/account/connections")

    answer = await site.post("/account/connections/google/remove", data={"csrf_token": csrf}, follow_redirects=False)

    assert answer.status_code == 303
    assert await db.scalar(select(SocialIdentity)) is not None
    assert "Add another usable sign-in method" in (await site.get("/account/connections")).text
