from datetime import timedelta

import pytest
from sqlalchemy import func, select

from enums.authentication_surface import AuthenticationSurface
from enums.user_role import UserRole
from enums.user_status import UserStatus
from helpers.authentication_error import AuthenticationError
from helpers.brand import of
from helpers.dates import now
from helpers.not_found_error import NotFoundError
from helpers.settings import settings
from helpers.validation_error import ValidationError
from models.email_login_challenge import EmailLoginChallenge
from models.outbound_email import OutboundEmail
from models.user import User
from services.auth_service import auth_service
from services.email_login_service import email_login_service
from services.social_login_service import social_login_service
from services.social_profile import SocialProfile
from services.user_service import user_service
from tests.factories import make_tenant


async def request(db, tenant, address="new@example.com", surface=AuthenticationSurface.SITE):
    challenge = await email_login_service.request(db, of(tenant), address, surface)
    message = await db.scalar(select(OutboundEmail).order_by(OutboundEmail.id.desc()).limit(1))

    return challenge.token, message.context["code"]


async def test_a_code_request_queues_mail_without_creating_an_account(db, tenant, email_login):
    token, code = await request(db, tenant)
    challenge = await db.scalar(select(EmailLoginChallenge))
    message = await db.scalar(select(OutboundEmail))

    assert await db.scalar(select(func.count()).select_from(User)) == 0
    assert len(code) == 6 and code.isascii() and code.isdigit()
    assert challenge.token == token
    assert code not in challenge.code_digest
    assert message.template == "sign-in-code"
    assert message.to_address == "new@example.com"


async def test_confirmation_creates_only_the_verified_email_and_account_defaults(db, tenant, email_login):
    token, code = await request(db, tenant)

    user = await email_login_service.confirm(db, of(tenant), token, code, AuthenticationSurface.SITE)

    assert user.email == "new@example.com"
    assert user.tenant_id == tenant.id
    assert user.status == UserStatus.ACTIVE
    assert user.role == UserRole.NORMAL
    assert user.password_hash == ""
    assert not user.has_password
    assert user.username is None
    assert user.first_name is None
    assert user.last_name is None
    assert user.language_id is None
    assert user.last_login_at is not None
    assert await db.scalar(select(func.count()).select_from(User)) == 1


async def test_confirmation_signs_in_the_account_that_already_has_the_address(db, tenant, member, email_login):
    identifier = member.id
    password_hash = member.password_hash
    token, code = await request(db, tenant, member.email)

    user = await email_login_service.confirm(db, of(tenant), token, code, AuthenticationSurface.SITE)

    assert user.id == identifier
    assert user.password_hash == password_hash
    assert await db.scalar(select(func.count()).select_from(User)) == 1


async def test_a_code_cannot_be_replayed(db, tenant, email_login):
    token, code = await request(db, tenant)
    await email_login_service.confirm(db, of(tenant), token, code, AuthenticationSurface.SITE)

    with pytest.raises(ValidationError, match="sign-in-code-invalid"):
        await email_login_service.confirm(db, of(tenant), token, code, AuthenticationSurface.SITE)


async def test_wrong_codes_exhaust_the_challenge_without_creating_an_account(db, tenant, email_login):
    token, code = await request(db, tenant)
    wrong = "111111" if code != "111111" else "222222"

    for _ in range(settings.authentication.email.max_attempts):
        with pytest.raises(ValidationError):
            await email_login_service.confirm(db, of(tenant), token, wrong, AuthenticationSurface.SITE)

    with pytest.raises(ValidationError):
        await email_login_service.confirm(db, of(tenant), token, code, AuthenticationSurface.SITE)

    assert await db.scalar(select(func.count()).select_from(User)) == 0
    assert (await db.scalar(select(EmailLoginChallenge))).attempts == settings.authentication.email.max_attempts


async def test_an_expired_code_cannot_create_an_account(db, tenant, email_login):
    token, code = await request(db, tenant)
    challenge = await db.scalar(select(EmailLoginChallenge))
    challenge.expires_at = now() - timedelta(seconds=1)
    await db.commit()

    with pytest.raises(ValidationError):
        await email_login_service.confirm(db, of(tenant), token, code, AuthenticationSurface.SITE)

    assert await db.scalar(select(func.count()).select_from(User)) == 0


async def test_requesting_again_during_the_cooldown_reuses_the_challenge_without_another_email(db, tenant, email_login):
    first, code = await request(db, tenant)
    second, _ = await request(db, tenant)

    assert first == second
    assert await db.scalar(select(func.count()).select_from(OutboundEmail)) == 1
    assert (await email_login_service.confirm(db, of(tenant), second, code, AuthenticationSurface.SITE)).email == "new@example.com"


async def test_a_resend_replaces_the_previous_challenge(db, tenant, email_login):
    old_token, old_code = await request(db, tenant)
    challenge = await db.scalar(select(EmailLoginChallenge))
    challenge.resend_at = now() - timedelta(seconds=1)
    await db.commit()

    token, code = await request(db, tenant)

    assert token != old_token
    assert await db.scalar(select(func.count()).select_from(OutboundEmail)) == 2

    with pytest.raises(ValidationError):
        await email_login_service.confirm(db, of(tenant), old_token, old_code, AuthenticationSurface.SITE)

    assert (await email_login_service.confirm(db, of(tenant), token, code, AuthenticationSurface.SITE)).email == "new@example.com"


async def test_confirming_a_pending_account_removes_the_unproved_password_and_old_credentials(db, tenant, member, email_login):
    member.status = UserStatus.PENDING
    member.recovery_token = "older-recovery"
    member.confirmation_token = "older-confirmation"
    epoch = member.session_epoch
    await db.commit()
    token, code = await request(db, tenant, member.email)

    user = await email_login_service.confirm(db, of(tenant), token, code, AuthenticationSurface.SITE)

    assert user.status == UserStatus.ACTIVE
    assert not user.has_password
    assert user.session_epoch == epoch + 1
    assert user.recovery_token is None
    assert user.confirmation_token is None


async def test_a_customer_cannot_open_the_panel_with_an_email_code(db, tenant, member, email_login):
    token, code = await request(db, tenant, member.email, AuthenticationSurface.ADMIN)

    with pytest.raises(AuthenticationError, match="panel-not-allowed"):
        await email_login_service.confirm(db, of(tenant), token, code, AuthenticationSurface.ADMIN)

    assert (await db.scalar(select(EmailLoginChallenge))).consumed_at is not None


async def test_an_unknown_panel_address_never_creates_an_operator_or_account(db, tenant, email_login):
    token, code = await request(db, tenant, surface=AuthenticationSurface.ADMIN)

    with pytest.raises(AuthenticationError, match="panel-not-allowed"):
        await email_login_service.confirm(db, of(tenant), token, code, AuthenticationSurface.ADMIN)

    assert await db.scalar(select(func.count()).select_from(User)) == 0


async def test_an_existing_operator_can_use_an_admin_code(db, tenant, administrator, email_login):
    token, code = await request(db, tenant, administrator.email, AuthenticationSurface.ADMIN)

    assert (await email_login_service.confirm(db, of(tenant), token, code, AuthenticationSurface.ADMIN)).id == administrator.id


async def test_an_email_code_is_bound_to_its_surface(db, tenant, administrator, email_login):
    token, code = await request(db, tenant, administrator.email)

    with pytest.raises(ValidationError):
        await email_login_service.confirm(db, of(tenant), token, code, AuthenticationSurface.ADMIN)


async def test_email_sign_in_is_disabled_by_default(db, tenant):
    with pytest.raises(NotFoundError, match="authentication-method-disabled"):
        await email_login_service.request(db, of(tenant), "new@example.com", AuthenticationSurface.SITE)


@pytest.mark.parametrize("state", ["spent", "expired", "exhausted"])
async def test_an_unusable_challenge_cannot_reopen_inside_the_resend_cooldown(db, tenant, email_login, state):
    token, code = await request(db, tenant)
    challenge = await db.scalar(select(EmailLoginChallenge))

    if state == "spent":
        challenge.consumed_at = now()

    if state == "expired":
        challenge.expires_at = now() - timedelta(seconds=1)

    if state == "exhausted":
        challenge.attempts = settings.authentication.email.max_attempts

    await db.commit()

    with pytest.raises(ValidationError, match="sign-in-code-wait"):
        await request(db, tenant)

    assert await db.scalar(select(func.count()).select_from(OutboundEmail)) == 1


@pytest.mark.parametrize("status", [UserStatus.BLOCKED, UserStatus.ERASED])
async def test_mailbox_proof_does_not_override_a_disabled_account(db, tenant, member, email_login, status):
    member.status = status
    await db.commit()
    token, code = await request(db, tenant, member.email)

    with pytest.raises(AuthenticationError):
        await email_login_service.confirm(db, of(tenant), token, code, AuthenticationSurface.SITE)

    assert (await db.scalar(select(EmailLoginChallenge))).consumed_at is not None


async def test_a_code_cannot_be_confirmed_on_another_brand(db, tenant, email_login):
    token, code = await request(db, tenant)
    another = await make_tenant(db, code="another", domain="another.example")

    with pytest.raises(ValidationError):
        await email_login_service.confirm(db, of(another), token, code, AuthenticationSurface.SITE)

    assert (await db.scalar(select(EmailLoginChallenge))).attempts == 0
    assert (await email_login_service.confirm(db, of(tenant), token, code, AuthenticationSurface.SITE)).tenant_id == tenant.id


async def test_a_single_brand_code_creates_an_account_in_global_scope(db, email_login, monkeypatch):
    monkeypatch.setattr(settings, "multi_tenant", False)
    brand = of(None)
    challenge = await email_login_service.request(db, brand, "single@example.com", AuthenticationSurface.SITE)
    message = await db.scalar(select(OutboundEmail))

    user = await email_login_service.confirm(db, brand, challenge.token, message.context["code"], AuthenticationSurface.SITE)

    assert user.tenant_id is None
    assert user.email == "single@example.com"


async def test_a_passwordless_account_cannot_clear_its_only_usable_email(db, tenant, email_login):
    token, code = await request(db, tenant)
    user = await email_login_service.confirm(db, of(tenant), token, code, AuthenticationSurface.SITE)

    with pytest.raises(ValidationError, match="last-sign-in-method"):
        await user_service.update(db, user.id, {"username": "reader", "email": None})


async def test_a_social_connection_allows_clearing_the_email_of_a_passwordless_account(db, tenant, email_login, social_login):
    from enums.social_provider import SocialProvider

    token, code = await request(db, tenant)
    user = await email_login_service.confirm(db, of(tenant), token, code, AuthenticationSurface.SITE)
    authorization = await social_login_service.start(db, of(tenant), SocialProvider.GOOGLE, AuthenticationSurface.SITE, "/account", user)
    await social_login_service.connect(db, authorization.attempt, SocialProfile("connected"))

    updated = await user_service.update(db, user.id, {"username": "reader", "email": None})

    assert updated.email is None
    assert not updated.has_password


async def test_a_passwordless_account_cannot_authenticate_with_a_password(db, tenant, email_login):
    token, code = await request(db, tenant)
    user = await email_login_service.confirm(db, of(tenant), token, code, AuthenticationSurface.SITE)

    with pytest.raises(AuthenticationError, match="invalid-credentials"):
        await auth_service.authenticate(db, tenant.id, user.email, "any-password")


async def test_a_disabled_social_connection_does_not_allow_removing_the_last_email(db, tenant, email_login, social_login):
    from enums.social_provider import SocialProvider

    token, code = await request(db, tenant)
    user = await email_login_service.confirm(db, of(tenant), token, code, AuthenticationSurface.SITE)
    authorization = await social_login_service.start(db, of(tenant), SocialProvider.GOOGLE, AuthenticationSurface.SITE, "/account", user=user)
    await social_login_service.connect(db, authorization.attempt, SocialProfile("connected"))
    social_login[SocialProvider.GOOGLE].enabled = False

    with pytest.raises(ValidationError, match="last-sign-in-method"):
        await user_service.update(db, user.id, {"username": "reader", "email": None})


async def test_account_erasure_removes_email_challenges_social_identities_and_pending_handoffs(db, tenant, member, email_login, social_login):
    from enums.social_provider import SocialProvider
    from models.login_ticket import LoginTicket
    from models.social_identity import SocialIdentity
    from models.social_login_attempt import SocialLoginAttempt
    from services.login_ticket_service import login_ticket_service

    await request(db, tenant, member.email)
    authorization = await social_login_service.start(db, of(tenant), SocialProvider.GOOGLE, AuthenticationSurface.SITE, "/account", user=member)
    await social_login_service.connect(db, authorization.attempt, SocialProfile("my-account"))
    await login_ticket_service.create(db, tenant.id, member, "browser")

    await user_service.erase(db, member)

    for model in (EmailLoginChallenge, SocialIdentity, SocialLoginAttempt, LoginTicket):
        assert await db.scalar(select(func.count()).select_from(model)) == 0
