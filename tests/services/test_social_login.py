import base64
import hashlib
from datetime import timedelta
from urllib.parse import parse_qs, urlsplit

import httpx2
import jwt
import pytest
from sqlalchemy import func, select

from enums.authentication_surface import AuthenticationSurface
from enums.social_provider import SocialProvider
from enums.user_role import UserRole
from helpers.app_error import AppError
from helpers.authentication_error import AuthenticationError
from helpers.authentication_helper import AuthenticationHelper
from helpers.brand import of
from helpers.dates import now
from helpers.not_found_error import NotFoundError
from helpers.permission_error import PermissionError
from helpers.security import decrypt
from helpers.validation_error import ValidationError
from models.social_identity import SocialIdentity
from models.user import User
from services.social_login_service import social_login_service
from services.social_profile import SocialProfile
from services.social_providers import PROVIDERS
from services.user_service import user_service
from tests.factories import make_tenant
from tests.helpers.social_login_test_helper import SocialLoginTestHelper


async def begun(db, tenant, provider=SocialProvider.GOOGLE, surface=AuthenticationSurface.SITE, user=None):
    authorization = await social_login_service.start(db, of(tenant), provider, surface, "/account", user)
    attempt = await social_login_service.consume(db, of(tenant), provider, authorization.state, authorization.browser)

    return authorization, attempt


@pytest.mark.parametrize("provider", list(SocialProvider))
async def test_each_provider_completes_its_real_protocol_with_stubbed_remote_responses(db, tenant, social_login, social_keys, monkeypatch, provider):
    authorization, attempt = await begun(db, tenant, provider)
    configuration = social_login[provider]
    seen = SocialLoginTestHelper.answer_provider(monkeypatch, provider, configuration, attempt, social_keys)

    user = await social_login_service.complete(db, attempt, "authorization-code")
    identity = await db.scalar(select(SocialIdentity))
    query = parse_qs(urlsplit(authorization.url).query)
    exchanged = parse_qs(seen[0].content.decode())

    assert user.role == UserRole.NORMAL
    assert not user.has_password
    assert user.tenant_id == tenant.id
    assert identity.user_id == user.id
    assert identity.subject == "provider-account"
    assert identity.provider == provider
    assert query["state"] == [authorization.state]
    assert query["redirect_uri"] == [attempt.redirect_uri]
    assert exchanged["code"] == ["authorization-code"]

    if PROVIDERS[provider].pkce:
        verifier = decrypt(attempt.verifier_encrypted)
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()

        assert query["code_challenge_method"] == ["S256"]
        assert query["code_challenge"] == [challenge]
        assert exchanged["code_verifier"] == [verifier]

    if provider in (SocialProvider.FACEBOOK, SocialProvider.INSTAGRAM, SocialProvider.MICROSOFT):
        assert user.email is None
        assert user.username.startswith(f"{provider.value}-")
    else:
        assert user.email == "social@example.com"

    if provider == SocialProvider.APPLE:
        assert query["response_mode"] == ["form_post"]
        secret = jwt.decode(exchanged["client_secret"][0], social_keys["apple_public"], algorithms=["ES256"], audience="https://appleid.apple.com", issuer="test-team")

        assert secret["sub"] == configuration.client_id

    if provider == SocialProvider.INSTAGRAM:
        assert query["enable_fb_login"] == ["false"]
        assert query["force_reauth"] == ["true"]


@pytest.mark.parametrize("changes", [{"nonce": "another-nonce"}, {"iss": "https://somebody-else.example"}, {"aud": "somebody-else"}, {"exp": 1}, {"iat": 9999999999}, {"sub": ""}])
async def test_invalid_oidc_claims_never_create_a_user(db, tenant, social_login, social_keys, monkeypatch, changes):
    _, attempt = await begun(db, tenant)
    SocialLoginTestHelper.answer_provider(monkeypatch, SocialProvider.GOOGLE, social_login[SocialProvider.GOOGLE], attempt, social_keys, claims=changes)

    with pytest.raises(AuthenticationError, match="social-response-invalid"):
        await social_login_service.complete(db, attempt, "authorization-code")

    assert await db.scalar(select(func.count()).select_from(User)) == 0
    assert await db.scalar(select(func.count()).select_from(SocialIdentity)) == 0


async def test_userinfo_must_name_the_same_subject_as_the_id_token(db, tenant, social_login, social_keys, monkeypatch):
    _, attempt = await begun(db, tenant)
    SocialLoginTestHelper.answer_provider(monkeypatch, SocialProvider.GOOGLE, social_login[SocialProvider.GOOGLE], attempt, social_keys, userinfo={"sub": "another-account"})

    with pytest.raises(AuthenticationError, match="social-response-invalid"):
        await social_login_service.complete(db, attempt, "authorization-code")


async def test_a_social_identity_is_not_silently_attached_to_an_existing_email(db, tenant, member, social_login):
    _, attempt = await begun(db, tenant)

    with pytest.raises(ValidationError, match="social-link-required"):
        await social_login_service.sign_in(db, attempt, SocialProfile("another-provider-account", member.email))

    assert await db.scalar(select(func.count()).select_from(SocialIdentity)) == 0


async def test_a_signed_in_account_can_connect_a_provider_and_use_it_to_sign_in(db, tenant, member, social_login):
    _, connecting = await begun(db, tenant, user=member)
    connected = await social_login_service.connect(db, connecting, SocialProfile("my-provider-account", "different@example.com"))
    _, signing_in = await begun(db, tenant)
    signed_in = await social_login_service.sign_in(db, signing_in, SocialProfile("my-provider-account"))

    assert connected.id == signed_in.id == member.id
    assert signed_in.email == member.email
    assert await db.scalar(select(func.count()).select_from(User)) == 1


async def test_connecting_the_same_provider_account_is_idempotent(db, tenant, member, social_login):
    _, attempt = await begun(db, tenant, user=member)

    await social_login_service.connect(db, attempt, SocialProfile("my-provider-account"))
    await social_login_service.connect(db, attempt, SocialProfile("my-provider-account"))

    assert await db.scalar(select(func.count()).select_from(SocialIdentity)) == 1


async def test_a_different_identity_from_a_connected_provider_is_not_substituted(db, tenant, member, social_login):
    _, attempt = await begun(db, tenant, user=member)
    await social_login_service.connect(db, attempt, SocialProfile("first-account"))

    with pytest.raises(ValidationError, match="social-provider-already-connected"):
        await social_login_service.connect(db, attempt, SocialProfile("second-account"))


async def test_starting_again_never_grants_panel_access_to_a_new_social_account(db, tenant, social_login):
    _, attempt = await begun(db, tenant, surface=AuthenticationSurface.ADMIN)

    with pytest.raises(AuthenticationError, match="panel-not-allowed"):
        await social_login_service.sign_in(db, attempt, SocialProfile("new-account", "new@example.com"))

    assert await db.scalar(select(func.count()).select_from(User)) == 0


async def test_a_social_state_cannot_be_used_from_another_browser_or_replayed(db, tenant, social_login):
    authorization = await social_login_service.start(db, of(tenant), SocialProvider.GOOGLE, AuthenticationSurface.SITE, "/account")

    with pytest.raises(AuthenticationError, match="social-attempt-invalid"):
        await social_login_service.consume(db, of(tenant), SocialProvider.GOOGLE, authorization.state, "another-browser")

    await social_login_service.consume(db, of(tenant), SocialProvider.GOOGLE, authorization.state, authorization.browser)

    with pytest.raises(AuthenticationError, match="social-attempt-invalid"):
        await social_login_service.consume(db, of(tenant), SocialProvider.GOOGLE, authorization.state, authorization.browser)


async def test_a_social_state_is_bound_to_the_provider_and_tenant(db, tenant, social_login):
    authorization = await social_login_service.start(db, of(tenant), SocialProvider.GOOGLE, AuthenticationSurface.SITE, "/account")
    another = await make_tenant(db, code="another", domain="another.example")

    with pytest.raises(AuthenticationError):
        await social_login_service.consume(db, of(another), SocialProvider.GOOGLE, authorization.state, authorization.browser)

    with pytest.raises(AuthenticationError):
        await social_login_service.consume(db, of(tenant), SocialProvider.GITHUB, authorization.state, authorization.browser)


async def test_an_expired_social_state_is_refused(db, tenant, social_login):
    authorization = await social_login_service.start(db, of(tenant), SocialProvider.GOOGLE, AuthenticationSurface.SITE, "/account")
    authorization.attempt.expires_at = now() - timedelta(seconds=1)
    await db.commit()

    with pytest.raises(AuthenticationError):
        await social_login_service.consume(db, of(tenant), SocialProvider.GOOGLE, authorization.state, authorization.browser)


async def test_a_password_change_ends_the_right_to_connect_an_in_flight_identity(db, tenant, member, social_login):
    _, attempt = await begun(db, tenant, user=member)
    member.session_epoch += 1
    await db.commit()

    with pytest.raises(AuthenticationError, match="social-attempt-invalid"):
        await social_login_service.connect(db, attempt, SocialProfile("another-account"))


async def test_the_last_social_method_of_a_passwordless_account_cannot_be_removed(db, tenant, social_login):
    _, attempt = await begun(db, tenant)
    user = await social_login_service.sign_in(db, attempt, SocialProfile("only-account"))

    with pytest.raises(ValidationError, match="last-sign-in-method"):
        await social_login_service.disconnect(db, user, SocialProvider.GOOGLE, AuthenticationSurface.SITE)


async def test_a_password_allows_removing_a_social_connection(db, tenant, member, social_login):
    _, attempt = await begun(db, tenant, user=member)
    await social_login_service.connect(db, attempt, SocialProfile("my-account"))

    await social_login_service.disconnect(db, member, SocialProvider.GOOGLE, AuthenticationSurface.SITE)

    assert await db.scalar(select(func.count()).select_from(SocialIdentity)) == 0


async def test_social_sign_in_is_disabled_by_default(db, tenant):
    with pytest.raises(NotFoundError, match="authentication-method-disabled"):
        await social_login_service.start(db, of(tenant), SocialProvider.GOOGLE, AuthenticationSurface.SITE, "/account")


async def test_google_accepts_both_official_current_issuer_spellings(db, tenant, social_login, social_keys, monkeypatch):
    _, attempt = await begun(db, tenant)
    SocialLoginTestHelper.answer_provider(monkeypatch, SocialProvider.GOOGLE, social_login[SocialProvider.GOOGLE], attempt, social_keys, claims={"iss": "accounts.google.com"})

    assert (await social_login_service.complete(db, attempt, "code")).email == "social@example.com"


@pytest.mark.parametrize("value,verified", [("true", True), (True, True), (False, False), ("false", False), (1, False)])
async def test_apple_accepts_only_its_documented_verified_email_values(db, tenant, social_login, social_keys, monkeypatch, value, verified):
    _, attempt = await begun(db, tenant, SocialProvider.APPLE)
    SocialLoginTestHelper.answer_provider(monkeypatch, SocialProvider.APPLE, social_login[SocialProvider.APPLE], attempt, social_keys, claims={"email_verified": value})

    user = await social_login_service.complete(db, attempt, "code")

    assert (user.email == "social@example.com") is verified


@pytest.mark.parametrize("payload", [[], {"access_token": ""}, {"access_token": 12}, {"token_type": "MAC"}, {"token_type": None}, {"error": {}}, {"error": ""}, {"id_token": None}, {"id_token": "malformed"}])
async def test_invalid_token_responses_cannot_create_an_account(db, tenant, social_login, social_keys, monkeypatch, payload):
    _, attempt = await begun(db, tenant)
    body = {"access_token": "provider-token", "token_type": "Bearer", **payload} if isinstance(payload, dict) else payload
    response = httpx2.Response(200, json=body)
    SocialLoginTestHelper.answer_provider(monkeypatch, SocialProvider.GOOGLE, social_login[SocialProvider.GOOGLE], attempt, social_keys, responses={PROVIDERS[SocialProvider.GOOGLE].token_url: response})

    with pytest.raises(AuthenticationError, match="social-response-invalid"):
        await social_login_service.complete(db, attempt, "code")

    assert await db.scalar(select(func.count()).select_from(User)) == 0


@pytest.mark.parametrize("stage,payload", [("keys", {"keys": []}), ("keys", {"keys": [{"kty": "RSA"}]}), ("keys", []), ("profile", []), ("profile", {"sub": True}), ("profile", {"sub": ""}), ("profile", {"sub": "provider-account", "email": "invalid", "email_verified": True})])
async def test_untrusted_keys_and_malformed_profiles_are_rejected(db, tenant, social_login, social_keys, monkeypatch, stage, payload):
    _, attempt = await begun(db, tenant)
    provider = PROVIDERS[SocialProvider.GOOGLE]
    endpoint = provider.jwks_url if stage == "keys" else provider.userinfo_url
    SocialLoginTestHelper.answer_provider(monkeypatch, SocialProvider.GOOGLE, social_login[SocialProvider.GOOGLE], attempt, social_keys, responses={endpoint: httpx2.Response(200, json=payload)})

    with pytest.raises(AuthenticationError, match="social-response-invalid"):
        await social_login_service.complete(db, attempt, "code")


async def test_an_id_token_with_an_invalid_signature_is_rejected(db, tenant, social_login, social_keys, monkeypatch):
    _, attempt = await begun(db, tenant)
    SocialLoginTestHelper.answer_provider(monkeypatch, SocialProvider.GOOGLE, social_login[SocialProvider.GOOGLE], attempt, social_keys, token_changes={"id_token": jwt.encode({"sub": "forged"}, "a-different-hmac-key-with-32-bytes", algorithm="HS256")})

    with pytest.raises(AuthenticationError):
        await social_login_service.complete(db, attempt, "code")


@pytest.mark.parametrize("failure", [httpx2.Response(503, text="Unavailable"), httpx2.Response(200, text="<html>Maintenance</html>"), httpx2.ConnectTimeout("Provider timed out"), httpx2.Response(200, json={"error": "invalid_grant"})])
async def test_remote_exchange_failures_return_an_application_error_without_creating_a_user(db, tenant, social_login, social_keys, monkeypatch, failure):
    _, attempt = await begun(db, tenant)
    SocialLoginTestHelper.answer_provider(monkeypatch, SocialProvider.GOOGLE, social_login[SocialProvider.GOOGLE], attempt, social_keys, responses={PROVIDERS[SocialProvider.GOOGLE].token_url: failure})

    with pytest.raises(AppError):
        await social_login_service.complete(db, attempt, "code")

    assert await db.scalar(select(func.count()).select_from(User)) == 0


@pytest.mark.parametrize("payload", [[], {}, {"access_token": "old-format"}, {"data": []}, {"data": ["invalid"]}, {"data": [{}, {}]}, {"data": [{"access_token": ""}]}, {"data": [{"access_token": 123}]}])
async def test_instagram_refuses_invalid_token_payloads(db, tenant, social_login, social_keys, monkeypatch, payload):
    _, attempt = await begun(db, tenant, SocialProvider.INSTAGRAM)
    SocialLoginTestHelper.answer_provider(monkeypatch, SocialProvider.INSTAGRAM, social_login[SocialProvider.INSTAGRAM], attempt, social_keys, responses={PROVIDERS[SocialProvider.INSTAGRAM].token_url: httpx2.Response(200, json=payload)})

    with pytest.raises(AuthenticationError):
        await social_login_service.complete(db, attempt, "code")


async def test_instagram_requires_the_profile_to_match_the_subject_returned_with_its_token(db, tenant, social_login, social_keys, monkeypatch):
    _, attempt = await begun(db, tenant, SocialProvider.INSTAGRAM)
    endpoint = f"https://graph.instagram.com/{social_login[SocialProvider.INSTAGRAM].facebook_api_version}/me"
    SocialLoginTestHelper.answer_provider(monkeypatch, SocialProvider.INSTAGRAM, social_login[SocialProvider.INSTAGRAM], attempt, social_keys, responses={endpoint: httpx2.Response(200, json={"user_id": "another-account"})})

    with pytest.raises(AuthenticationError, match="social-response-invalid"):
        await social_login_service.complete(db, attempt, "code")


@pytest.mark.parametrize("emails", [{}, ["invalid-entry"]])
async def test_github_refuses_an_invalid_email_collection(db, tenant, social_login, social_keys, monkeypatch, emails):
    _, attempt = await begun(db, tenant, SocialProvider.GITHUB)
    SocialLoginTestHelper.answer_provider(monkeypatch, SocialProvider.GITHUB, social_login[SocialProvider.GITHUB], attempt, social_keys, responses={"https://api.github.com/user/emails": httpx2.Response(200, json=emails)})

    with pytest.raises(AuthenticationError):
        await social_login_service.complete(db, attempt, "code")


async def test_github_without_a_primary_verified_email_keeps_the_address_empty(db, tenant, social_login, social_keys, monkeypatch):
    _, attempt = await begun(db, tenant, SocialProvider.GITHUB)
    emails = [{"email": "unverified@example.com", "primary": True, "verified": False}, {"email": "secondary@example.com", "primary": False, "verified": True}]
    SocialLoginTestHelper.answer_provider(monkeypatch, SocialProvider.GITHUB, social_login[SocialProvider.GITHUB], attempt, social_keys, responses={"https://api.github.com/user/emails": httpx2.Response(200, json=emails)})

    user = await social_login_service.complete(db, attempt, "code")

    assert user.email is None
    assert user.username.startswith("github-")


async def test_email_code_availability_allows_removing_a_passwordless_social_connection(db, tenant, social_login, email_login):
    _, attempt = await begun(db, tenant)
    user = await social_login_service.sign_in(db, attempt, SocialProfile("account", "mail@example.com"))

    await social_login_service.disconnect(db, user, SocialProvider.GOOGLE, AuthenticationSurface.SITE)

    assert not await social_login_service.connections(db, user)


async def test_another_enabled_connection_allows_removing_one_social_method(db, tenant, social_login):
    _, attempt = await begun(db, tenant)
    user = await social_login_service.sign_in(db, attempt, SocialProfile("google-account"))
    _, connection = await begun(db, tenant, SocialProvider.GITHUB, user=user)
    await social_login_service.connect(db, connection, SocialProfile("github-account"))

    await social_login_service.disconnect(db, user, SocialProvider.GOOGLE, AuthenticationSurface.SITE)

    assert [identity.provider for identity in await social_login_service.connections(db, user)] == [SocialProvider.GITHUB]


async def test_a_connection_cannot_start_in_another_tenant(db, tenant, member, social_login):
    another = await make_tenant(db, code="another", domain="another.example")

    with pytest.raises(PermissionError, match="account-of-another-brand"):
        await begun(db, another, user=member)


async def test_a_deleted_account_never_reaches_session_creation(db, tenant):
    with pytest.raises(AuthenticationError, match="invalid-credentials"):
        await AuthenticationHelper.signed_in(db, None, AuthenticationSurface.SITE, tenant.id)


async def test_moving_an_account_to_global_scope_moves_its_social_identity_too(db, tenant, member, social_login):
    _, attempt = await begun(db, tenant, user=member)
    await social_login_service.connect(db, attempt, SocialProfile("my-account"))

    await user_service.update(db, member.id, {"tenant_id": None})

    assert (await db.scalar(select(SocialIdentity))).tenant_id is None


async def test_an_unknown_social_state_is_refused_before_any_provider_exchange(db, tenant, social_login):
    with pytest.raises(AuthenticationError, match="social-attempt-invalid"):
        await social_login_service.consume(db, of(tenant), SocialProvider.GOOGLE, "unknown-state", "unknown-browser")


async def test_an_unreadable_pkce_verifier_cannot_be_exchanged(db, tenant, social_login):
    _, attempt = await begun(db, tenant)
    attempt.verifier_encrypted = "unreadable"

    with pytest.raises(AuthenticationError, match="social-attempt-invalid"):
        await social_login_service.complete(db, attempt, "code")


async def test_concurrent_identity_creation_keeps_only_the_winning_account(db, tenant, social_login, monkeypatch):
    from unittest.mock import AsyncMock

    _, first = await begun(db, tenant)
    winner = await social_login_service.sign_in(db, first, SocialProfile("same-account"))
    identifier = winner.id
    _, second = await begun(db, tenant)
    monkeypatch.setattr(social_login_service, "identity", AsyncMock(return_value=None))

    signed_in = await social_login_service.sign_in(db, second, SocialProfile("same-account"))

    assert signed_in.id == identifier
    assert await db.scalar(select(func.count()).select_from(User)) == 1
    assert await db.scalar(select(func.count()).select_from(SocialIdentity)) == 1


async def test_a_disabled_connected_provider_remains_visible_to_its_owner(db, tenant, member, social_login):
    _, attempt = await begun(db, tenant, user=member)
    await social_login_service.connect(db, attempt, SocialProfile("connected"))
    social_login[SocialProvider.GOOGLE].enabled = False

    options = AuthenticationHelper.connections(AuthenticationSurface.SITE, await social_login_service.connections(db, member))
    google = next(option for option in options if option["provider"] == SocialProvider.GOOGLE)

    assert google["connected"]
    assert not google["enabled"]


async def test_a_password_change_while_a_connection_waits_for_the_account_lock_refuses_the_link(db, tenant, member, social_login, monkeypatch):
    from sqlalchemy import update

    _, attempt = await begun(db, tenant, user=member)
    hold = user_service.hold

    async def changed_before_lock(session, identifier):
        await session.execute(update(User).where(User.id == identifier).values(session_epoch=User.session_epoch + 1).execution_options(synchronize_session=False))
        await hold(session, identifier)

    monkeypatch.setattr(user_service, "hold", changed_before_lock)

    with pytest.raises(AuthenticationError, match="social-attempt-invalid"):
        await social_login_service.connect(db, attempt, SocialProfile("new-account"))

    assert await db.scalar(select(func.count()).select_from(SocialIdentity)) == 0


async def test_social_subjects_are_case_sensitive_and_never_normalized(db, tenant, social_login):
    _, first = await begun(db, tenant)
    upper = await social_login_service.sign_in(db, first, SocialProfile("ProviderAccount"))
    _, second = await begun(db, tenant)
    lower = await social_login_service.sign_in(db, second, SocialProfile("provideraccount"))

    assert upper.id != lower.id
    assert await db.scalar(select(func.count()).select_from(SocialIdentity)) == 2
