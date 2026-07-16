import pytest

from fastkit_core.errors.exceptions import AuthenticationError, RateLimitError
from fastkit_auth.errors import ACCOUNT_INACTIVE, ACCOUNT_LOCKED, AMBIGUOUS_IDENTITY, INVALID_CREDENTIALS


async def make_user(accounts, passwords, tenant_id, email, password="correct horse battery", is_root=False, is_active=True):
    user = await accounts.create_user(tenant_id=tenant_id, identifiers=[("email", email)], is_root=is_root, password_hash=passwords.hash(password))

    if not is_active:
        async with accounts._session_factory() as session:
            from fastkit_accounts.models import User

            stored = await session.get(User, user.id)
            stored.is_active = False
            await session.commit()

    return user


async def test_successful_login(auth_service, accounts, passwords):
    await make_user(accounts, passwords, tenant_id=1, email="owner@acme.com")

    result = await auth_service.login("email", "owner@acme.com", "correct horse battery", requested_tenant_id=1, ip_address="1.1.1.1")

    assert result.user.email == "owner@acme.com"
    assert result.token
    assert result.session_token
    assert result.effective_tenant_id == 1
    assert result.session.status == "active"


async def test_login_wrong_password(auth_service, accounts, passwords):
    await make_user(accounts, passwords, tenant_id=1, email="owner@acme.com")

    with pytest.raises(AuthenticationError) as exc:
        await auth_service.login("email", "owner@acme.com", "wrong-password", requested_tenant_id=1)

    assert exc.value.error_code is INVALID_CREDENTIALS


async def test_login_unknown_identifier_is_generic(auth_service):
    with pytest.raises(AuthenticationError) as exc:
        await auth_service.login("email", "ghost@acme.com", "whatever", requested_tenant_id=1)

    assert exc.value.error_code is INVALID_CREDENTIALS


async def test_login_unknown_identifier_type_is_generic_not_a_500(auth_service):
    with pytest.raises(AuthenticationError) as exc:
        await auth_service.login("bogus-type", "x@y.com", "whatever", requested_tenant_id=1)

    assert exc.value.error_code is INVALID_CREDENTIALS


async def test_login_inactive_account(auth_service, accounts, passwords):
    await make_user(accounts, passwords, tenant_id=1, email="off@acme.com", is_active=False)

    with pytest.raises(AuthenticationError) as exc:
        await auth_service.login("email", "off@acme.com", "correct horse battery", requested_tenant_id=1)

    assert exc.value.error_code is ACCOUNT_INACTIVE


async def test_brute_force_locks_account(auth_service, accounts, passwords):
    await make_user(accounts, passwords, tenant_id=1, email="lock@acme.com")

    for _ in range(3):
        with pytest.raises(AuthenticationError):
            await auth_service.login("email", "lock@acme.com", "bad", requested_tenant_id=1)

    with pytest.raises(AuthenticationError) as exc:
        await auth_service.login("email", "lock@acme.com", "correct horse battery", requested_tenant_id=1)

    assert exc.value.error_code is ACCOUNT_LOCKED


async def test_lock_expires_after_window(auth_service, accounts, passwords, clock):
    await make_user(accounts, passwords, tenant_id=1, email="lock2@acme.com")

    for _ in range(3):
        with pytest.raises(AuthenticationError):
            await auth_service.login("email", "lock2@acme.com", "bad", requested_tenant_id=1)

    clock.advance(1000)

    result = await auth_service.login("email", "lock2@acme.com", "correct horse battery", requested_tenant_id=1)

    assert result.token


async def test_successful_login_resets_failures(auth_service, accounts, passwords):
    await make_user(accounts, passwords, tenant_id=1, email="reset@acme.com")

    with pytest.raises(AuthenticationError):
        await auth_service.login("email", "reset@acme.com", "bad", requested_tenant_id=1)

    result = await auth_service.login("email", "reset@acme.com", "correct horse battery", requested_tenant_id=1)

    assert result.user.failed_login_count == 0
    assert result.user.last_login_at is not None


async def test_rate_limit_triggers(auth_service, accounts, passwords):
    await make_user(accounts, passwords, tenant_id=1, email="rl@acme.com")

    for _ in range(5):
        with pytest.raises(AuthenticationError):
            await auth_service.login("email", "rl@acme.com", "bad", requested_tenant_id=1, ip_address="9.9.9.9")

    with pytest.raises(RateLimitError):
        await auth_service.login("email", "rl@acme.com", "bad", requested_tenant_id=1, ip_address="9.9.9.9")


async def test_global_user_logs_into_requested_tenant(auth_service, accounts, passwords):
    await make_user(accounts, passwords, tenant_id=0, email="root@platform.com", is_root=True)

    result = await auth_service.login("email", "root@platform.com", "correct horse battery", requested_tenant_id=7)

    assert result.effective_tenant_id == 7
    assert result.user.is_root is True


async def test_ambiguous_identity_when_local_and_global_match(auth_service, accounts, passwords):
    await make_user(accounts, passwords, tenant_id=1, email="dup@acme.com", password="shared-secret-12")
    await make_user(accounts, passwords, tenant_id=0, email="dup@acme.com", password="shared-secret-12")

    with pytest.raises(AuthenticationError) as exc:
        await auth_service.login("email", "dup@acme.com", "shared-secret-12", requested_tenant_id=1)

    assert exc.value.error_code is AMBIGUOUS_IDENTITY


async def test_logout_revokes_session(auth_service, accounts, passwords):
    await make_user(accounts, passwords, tenant_id=1, email="bye@acme.com")
    result = await auth_service.login("email", "bye@acme.com", "correct horse battery", requested_tenant_id=1)

    _, raw_token = await auth_service._sessions.create(result.user.id, 1, 1)

    assert await auth_service.logout(raw_token) is True
    assert await auth_service.logout("unknown-token") is False
