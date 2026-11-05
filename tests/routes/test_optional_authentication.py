import pytest
from sqlalchemy import func, select

from config.social_login_settings import SocialLoginSettings
from enums.social_provider import SocialProvider
from helpers.authentication_cookie_helper import AuthenticationCookieHelper
from helpers.settings import settings
from models.outbound_email import OutboundEmail
from models.social_identity import SocialIdentity
from models.user import User
from services.login_ticket_service import login_ticket_service


async def test_the_api_reports_no_optional_sign_in_methods_by_default(client):
    answer = await client.get("/api/auth/methods")

    assert answer.status_code == 200
    assert answer.json() == {"emailCode": False, "social": []}


async def test_method_metadata_exposes_labels_without_credentials(client, monkeypatch):
    monkeypatch.setattr(settings.authentication, "social", {SocialProvider.GOOGLE: SocialLoginSettings(enabled=True, client_id="public-id", client_secret="private-client-secret", admin=False)})

    assert (await client.get("/api/auth/methods")).json() == {"emailCode": False, "social": [{"provider": "google", "label": "Google"}]}
    assert (await client.get("/api/auth/methods?surface=admin")).json() == {"emailCode": False, "social": []}


async def test_the_email_api_creates_the_account_only_after_the_code_is_confirmed(client, db, tenant, tenant_headers, email_login):
    requested = await client.post("/api/auth/email/request", json={"email": "new@example.com"}, headers=tenant_headers)

    assert requested.status_code == 200
    assert "code" not in requested.json()
    assert await db.scalar(select(func.count()).select_from(User)) == 0

    message = await db.scalar(select(OutboundEmail))
    answer = await client.post("/api/auth/email/confirm", json={"challenge": requested.json()["challenge"], "code": message.context["code"]}, headers=tenant_headers)

    assert answer.status_code == 200
    assert answer.json()["token"]
    assert answer.json()["user"]["email"] == "new@example.com"
    assert answer.json()["user"]["hasPassword"] is False
    assert answer.json()["user"]["firstName"] is None


async def test_an_admin_code_resolves_the_brand_by_host_and_requires_an_existing_operator(client, db, tenant, administrator, email_login):
    headers = {"Host": tenant.domain}
    requested = await client.post("/api/auth/email/request", json={"email": administrator.email, "surface": "admin"}, headers=headers)
    message = await db.scalar(select(OutboundEmail))
    answer = await client.post("/api/auth/email/confirm", json={"challenge": requested.json()["challenge"], "code": message.context["code"], "surface": "admin"}, headers=headers)

    assert answer.status_code == 200
    assert answer.json()["user"]["token"] == administrator.token


async def test_email_endpoints_are_unavailable_when_the_method_is_disabled(client, tenant_headers):
    requested = await client.post("/api/auth/email/request", json={"email": "new@example.com"}, headers=tenant_headers)

    assert requested.status_code == 404
    assert requested.json()["code"] == "error.authentication-method-disabled"


@pytest.mark.parametrize("payload", [{"email": "invalid"}, {"email": "new@example.com", "role": "administrator"}, {"email": "new@example.com", "surface": "unknown"}])
async def test_email_sign_in_rejects_invalid_input_and_unrequested_roles(client, tenant_headers, email_login, payload):
    assert (await client.post("/api/auth/email/request", json=payload, headers=tenant_headers)).status_code == 422


async def test_an_admin_ticket_cannot_be_redeemed_without_its_browser_cookie(client, db, tenant, administrator):
    ticket = await login_ticket_service.create(db, tenant.id, administrator, "browser-proof")
    payload = {"ticket": ticket}
    headers = {"Host": tenant.domain}

    assert (await client.post("/api/admin/social/redeem", json=payload, headers=headers)).status_code == 401

    client.cookies.set(AuthenticationCookieHelper.name(ticket), "browser-proof")
    answer = await client.post("/api/admin/social/redeem", json=payload, headers=headers)

    assert answer.status_code == 200
    assert answer.json()["user"]["token"] == administrator.token
    assert (await client.post("/api/admin/social/redeem", json=payload, headers=headers)).status_code == 401


async def test_requesting_a_code_requires_the_configured_captcha(client, tenant_headers, email_login, monkeypatch):
    from unittest.mock import AsyncMock

    monkeypatch.setattr("routes.authentication.captcha.verify", AsyncMock(return_value=False))

    answer = await client.post("/api/auth/email/request", json={"email": "reader@example.com"}, headers=tenant_headers)

    assert answer.status_code == 422
    assert answer.json()["code"] == "error.captcha-invalid"


async def test_admin_email_login_on_an_unknown_host_is_refused(client, email_login):
    answer = await client.post("/api/auth/email/request", json={"email": "reader@example.com", "surface": "admin"}, headers={"Host": "unknown.example"})

    assert answer.status_code == 404


async def test_the_api_can_start_and_remove_only_the_callers_social_connection(client, db, tenant, tenant_headers, member, member_headers, social_login):
    from enums.authentication_surface import AuthenticationSurface
    from helpers.brand import of
    from services.social_login_service import social_login_service
    from services.social_profile import SocialProfile

    headers = {**tenant_headers, **member_headers}
    start = await client.post("/api/account/social-connections/google/start", json={"surface": "site"}, headers=headers)

    assert start.status_code == 200
    assert start.json()["authorizationUrl"].startswith("https://accounts.google.com/")
    assert "HttpOnly" in start.headers["set-cookie"]

    authorization = await social_login_service.start(db, of(tenant), SocialProvider.GOOGLE, AuthenticationSurface.SITE, "/account", user=member)
    await social_login_service.connect(db, authorization.attempt, SocialProfile("my-account"))
    listed = await client.get("/api/account/social-connections", headers=headers)

    assert next(item for item in listed.json() if item["provider"] == "google")["connected"]
    assert (await client.delete("/api/account/social-connections/google", headers=headers)).status_code == 204
    assert await db.scalar(select(SocialIdentity)) is None
