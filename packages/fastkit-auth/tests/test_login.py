import pytest

from fastkit_core.errors.exceptions import AuthenticationError, RateLimitError
from fastkit_auth.errors import (
    ACCOUNT_INACTIVE,
    ACCOUNT_LOCKED,
    AMBIGUOUS_IDENTITY,
    INVALID_CREDENTIALS,
)


async def make_user(
    accounts,
    passwords,
    tenant_id,
    email,
    password="correct horse battery",
    is_root=False,
    is_active=True,
):
    user = await accounts.create_user(
        tenant_id=tenant_id,
        identifiers=[("email", email)],
        is_root=is_root,
        password_hash=passwords.hash(password),
    )

    if not is_active:
        async with accounts._database.session_factory() as session:
            from fastkit_accounts.models import User

            stored = await session.get(User, user.id)
            stored.is_active = False
            await session.commit()

    return user


async def test_successful_login(auth_service, accounts, passwords):
    await make_user(accounts, passwords, tenant_id=1, email="owner@acme.com")

    result = await auth_service.login(
        "email",
        "owner@acme.com",
        "correct horse battery",
        requested_tenant_id=1,
        ip_address="1.1.1.1",
    )

    assert result.user.email == "owner@acme.com"
    assert result.token
    assert result.session_token
    assert result.effective_tenant_id == 1
    assert result.session.status == "active"


async def test_successful_login_rehashes_when_parameters_changed(
    auth_service, accounts, passwords, monkeypatch
):
    from fastkit_accounts.models import User

    user = await make_user(accounts, passwords, tenant_id=1, email="rehash@acme.com")
    original_hash = user.password_hash

    monkeypatch.setattr(passwords, "needs_rehash", lambda password_hash: True)

    result = await auth_service.login(
        "email", "rehash@acme.com", "correct horse battery", requested_tenant_id=1
    )

    assert result.user.password_hash != original_hash
    assert passwords.verify(result.user.password_hash, "correct horse battery")

    async with accounts._database.session_factory() as session:
        stored = await session.get(User, user.id)

        assert stored.password_hash == result.user.password_hash


async def test_login_wrong_password(auth_service, accounts, passwords):
    await make_user(accounts, passwords, tenant_id=1, email="owner@acme.com")

    with pytest.raises(AuthenticationError) as exc:
        await auth_service.login(
            "email", "owner@acme.com", "wrong-password", requested_tenant_id=1
        )

    assert exc.value.error_code is INVALID_CREDENTIALS


async def test_login_passwordless_account_still_runs_dummy_verify(
    auth_service, accounts, passwords, monkeypatch
):
    await accounts.create_user(
        tenant_id=1, identifiers=[("email", "social@acme.com")], password_hash=None
    )

    calls = []
    monkeypatch.setattr(
        passwords, "dummy_verify", lambda password: calls.append(password)
    )

    with pytest.raises(AuthenticationError) as exc:
        await auth_service.login(
            "email", "social@acme.com", "whatever", requested_tenant_id=1
        )

    assert exc.value.error_code is INVALID_CREDENTIALS
    assert calls == ["whatever"]


async def test_login_unknown_identifier_is_generic(auth_service):
    with pytest.raises(AuthenticationError) as exc:
        await auth_service.login(
            "email", "ghost@acme.com", "whatever", requested_tenant_id=1
        )

    assert exc.value.error_code is INVALID_CREDENTIALS


async def test_login_unknown_identifier_type_is_generic_not_a_500(auth_service):
    with pytest.raises(AuthenticationError) as exc:
        await auth_service.login(
            "bogus-type", "x@y.com", "whatever", requested_tenant_id=1
        )

    assert exc.value.error_code is INVALID_CREDENTIALS


async def test_login_inactive_account(auth_service, accounts, passwords):
    await make_user(
        accounts, passwords, tenant_id=1, email="off@acme.com", is_active=False
    )

    with pytest.raises(AuthenticationError) as exc:
        await auth_service.login(
            "email", "off@acme.com", "correct horse battery", requested_tenant_id=1
        )

    assert exc.value.error_code is ACCOUNT_INACTIVE


async def test_brute_force_locks_account(auth_service, accounts, passwords):
    await make_user(accounts, passwords, tenant_id=1, email="lock@acme.com")

    for _ in range(3):
        with pytest.raises(AuthenticationError):
            await auth_service.login(
                "email", "lock@acme.com", "bad", requested_tenant_id=1
            )

    with pytest.raises(AuthenticationError) as exc:
        await auth_service.login(
            "email", "lock@acme.com", "correct horse battery", requested_tenant_id=1
        )

    assert exc.value.error_code is ACCOUNT_LOCKED


async def test_lock_expires_after_window(auth_service, accounts, passwords, clock):
    await make_user(accounts, passwords, tenant_id=1, email="lock2@acme.com")

    for _ in range(3):
        with pytest.raises(AuthenticationError):
            await auth_service.login(
                "email", "lock2@acme.com", "bad", requested_tenant_id=1
            )

    clock.advance(1000)

    result = await auth_service.login(
        "email", "lock2@acme.com", "correct horse battery", requested_tenant_id=1
    )

    assert result.token


async def test_successful_login_resets_failures(auth_service, accounts, passwords):
    await make_user(accounts, passwords, tenant_id=1, email="reset@acme.com")

    with pytest.raises(AuthenticationError):
        await auth_service.login(
            "email", "reset@acme.com", "bad", requested_tenant_id=1
        )

    result = await auth_service.login(
        "email", "reset@acme.com", "correct horse battery", requested_tenant_id=1
    )

    assert result.user.failed_login_count == 0
    assert result.user.last_login_at is not None


async def test_rate_limit_triggers(auth_service, accounts, passwords):
    await make_user(accounts, passwords, tenant_id=1, email="rl@acme.com")

    for _ in range(5):
        with pytest.raises(AuthenticationError):
            await auth_service.login(
                "email",
                "rl@acme.com",
                "bad",
                requested_tenant_id=1,
                ip_address="9.9.9.9",
            )

    with pytest.raises(RateLimitError):
        await auth_service.login(
            "email", "rl@acme.com", "bad", requested_tenant_id=1, ip_address="9.9.9.9"
        )


async def test_global_user_logs_into_requested_tenant(
    auth_service, accounts, passwords
):
    await make_user(
        accounts, passwords, tenant_id=0, email="root@platform.com", is_root=True
    )

    result = await auth_service.login(
        "email", "root@platform.com", "correct horse battery", requested_tenant_id=7
    )

    assert result.effective_tenant_id == 7
    assert result.user.is_root is True


async def test_ambiguous_identity_when_local_and_global_match(
    auth_service, accounts, passwords
):
    await make_user(
        accounts,
        passwords,
        tenant_id=1,
        email="dup@acme.com",
        password="shared-secret-12",
    )
    await make_user(
        accounts,
        passwords,
        tenant_id=0,
        email="dup@acme.com",
        password="shared-secret-12",
    )

    with pytest.raises(AuthenticationError) as exc:
        await auth_service.login(
            "email", "dup@acme.com", "shared-secret-12", requested_tenant_id=1
        )

    assert exc.value.error_code is AMBIGUOUS_IDENTITY


async def test_logout_revokes_session(auth_service, accounts, passwords):
    await make_user(accounts, passwords, tenant_id=1, email="bye@acme.com")
    result = await auth_service.login(
        "email", "bye@acme.com", "correct horse battery", requested_tenant_id=1
    )

    _, raw_token = await auth_service._sessions.create(result.user.id, 1, 1)

    assert await auth_service.logout(raw_token) is True
    assert await auth_service.logout("unknown-token") is False


async def test_login_enforces_the_captcha(database, accounts, passwords, clock):
    import json

    from fastkit_auth.captcha.image import ImageCaptchaProvider
    from fastkit_auth.ratelimit import RateLimiter
    from fastkit_auth.service import AuthService
    from fastkit_auth.sessions import SessionService
    from fastkit_auth.store import MemoryKeyValueStore
    from fastkit_auth.tokens import TokenService

    store = MemoryKeyValueStore()
    captcha = ImageCaptchaProvider(store, clock=clock)
    service = AuthService(
        database,
        accounts,
        passwords,
        SessionService(database, ttl_seconds=3600, clock=clock),
        TokenService(secret_key="test-secret", ttl_seconds=3600),
        RateLimiter(
            MemoryKeyValueStore(clock=lambda: 0.0),
            max_attempts=5,
            window_seconds=60,
            clock=lambda: 0.0,
        ),
        captcha,
        clock=clock,
    )
    await make_user(accounts, passwords, tenant_id=1, email="cap@acme.com")

    with pytest.raises(AuthenticationError, match="required"):
        await service.login(
            "email", "cap@acme.com", "correct horse battery", requested_tenant_id=1
        )

    challenge = await captcha.new_challenge()
    stored = await store.get(captcha._store_key(challenge["challenge_id"]))
    code = json.loads(stored.decode("utf-8"))["code"]
    result = await service.login(
        "email",
        "cap@acme.com",
        "correct horse battery",
        requested_tenant_id=1,
        captcha={"challenge_id": challenge["challenge_id"], "answer": code},
    )

    assert result.token


async def test_on_success_is_a_noop_when_the_user_was_deleted_concurrently(
    auth_service, accounts, passwords
):
    from fastkit_accounts.models import User

    user = await make_user(accounts, passwords, tenant_id=1, email="ghost@acme.com")

    async with accounts._database.session_factory() as session:
        stored = await session.get(User, user.id)
        await session.delete(stored)
        await session.commit()

    await auth_service._on_success(user, "correct horse battery")

    assert user.last_login_at is None
