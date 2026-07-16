from datetime import datetime, timezone

import pytest

from fastkit_core.errors.exceptions import AuthenticationError, RateLimitError, ValidationError
from fastkit_auth.passwords import PasswordHashService
from fastkit_auth.ratelimit import RateLimiter
from fastkit_auth.recaptcha import RecaptchaConfig, RecaptchaVerifier, StaticRecaptchaClient
from fastkit_auth.tokens import TokenService


def test_ensure_aware():
    from fastkit_auth.helpers import ensure_aware

    naive = datetime(2026, 1, 1, 12, 0, 0)
    aware = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    assert ensure_aware(naive).tzinfo is timezone.utc
    assert ensure_aware(aware) is aware


def test_password_hash_and_verify():
    service = PasswordHashService(min_length=8)
    hashed = service.hash("correct horse")

    assert service.verify(hashed, "correct horse")
    assert not service.verify(hashed, "wrong")
    assert not service.needs_rehash(hashed)


def test_password_policy_enforced():
    service = PasswordHashService(min_length=12)

    with pytest.raises(ValidationError):
        service.hash("short")


def test_password_policy_rejects_too_long():
    service = PasswordHashService(min_length=4, max_length=16)

    with pytest.raises(ValidationError):
        service.hash("x" * 17)


def test_password_verify_rejects_garbage_hash():
    service = PasswordHashService(min_length=4)

    assert not service.verify("not-a-valid-hash", "whatever")


def test_dummy_verify_builds_and_reuses_a_throwaway_hash():
    service = PasswordHashService(min_length=4)

    service.dummy_verify("first attempt")
    first = service._dummy_hash

    service.dummy_verify("second attempt")

    assert first is not None
    assert service._dummy_hash is first


def test_token_issue_and_verify():
    service = TokenService(secret_key="secret", ttl_seconds=3600)
    token = service.issue("user-1", 0, 5, "session-1")

    claims = service.verify(token)

    assert claims["sub"] == "user-1"
    assert claims["etid"] == 5
    assert claims["sid"] == "session-1"


def test_token_expired_is_rejected():
    past = datetime(2000, 1, 1, tzinfo=timezone.utc)
    service = TokenService(secret_key="secret", ttl_seconds=1)
    token = service.issue("user-1", 0, 0, "s", issued_at=past)

    with pytest.raises(AuthenticationError, match="expired"):
        service.verify(token)


def test_token_tampered_is_rejected():
    service = TokenService(secret_key="secret")

    with pytest.raises(AuthenticationError, match="invalid"):
        service.verify("garbage.token.value")


def test_token_wrong_secret_is_rejected():
    issued = TokenService(secret_key="secret-a").issue("u", 0, 0, "s")

    with pytest.raises(AuthenticationError):
        TokenService(secret_key="secret-b").verify(issued)


def test_rate_limiter_blocks_after_max():
    times = iter([0.0, 0.0, 0.0])
    limiter = RateLimiter(max_attempts=2, window_seconds=60, clock=lambda: next(times))

    limiter.hit("ip", 1, "email:a")
    limiter.hit("ip", 1, "email:a")

    with pytest.raises(RateLimitError):
        limiter.hit("ip", 1, "email:a")


def test_rate_limiter_window_expires():
    clock = {"now": 0.0}
    limiter = RateLimiter(max_attempts=1, window_seconds=10, clock=lambda: clock["now"])

    limiter.hit("ip")
    clock["now"] = 20.0
    limiter.hit("ip")


def test_rate_limiter_default_clock():
    limiter = RateLimiter(max_attempts=1, window_seconds=60)

    limiter.hit("ip")

    with pytest.raises(RateLimitError):
        limiter.hit("ip")


def test_rate_limiter_reset():
    limiter = RateLimiter(max_attempts=1, window_seconds=60, clock=lambda: 0.0)
    limiter.hit("ip")
    limiter.reset("ip")
    limiter.hit("ip")


def _verifier(enabled=True, action="admin_login", score=0.5, hostnames=()):
    config = RecaptchaConfig(enabled=enabled, action=action, minimum_score=score, allowed_hostnames=hostnames)

    return config


async def test_recaptcha_disabled_passes():
    verifier = RecaptchaVerifier(_verifier(enabled=False), StaticRecaptchaClient({}))

    await verifier.verify(None)


async def test_recaptcha_missing_token():
    verifier = RecaptchaVerifier(_verifier(), StaticRecaptchaClient({"success": True}))

    with pytest.raises(AuthenticationError, match="required"):
        await verifier.verify(None)


async def test_recaptcha_success():
    client = StaticRecaptchaClient({"success": True, "action": "admin_login", "score": 0.9, "hostname": "admin.example.com"})
    verifier = RecaptchaVerifier(_verifier(hostnames=("admin.example.com",)), client)

    await verifier.verify("token-1")


async def test_recaptcha_duplicate_token_rejected():
    verifier = RecaptchaVerifier(_verifier(), StaticRecaptchaClient({"success": True, "action": "admin_login", "score": 0.9}))

    await verifier.verify("token-1")

    with pytest.raises(AuthenticationError, match="already used"):
        await verifier.verify("token-1")


async def test_recaptcha_failure_flag():
    verifier = RecaptchaVerifier(_verifier(), StaticRecaptchaClient({"success": False}))

    with pytest.raises(AuthenticationError, match="verification failed"):
        await verifier.verify("token-x")


async def test_recaptcha_action_mismatch():
    verifier = RecaptchaVerifier(_verifier(), StaticRecaptchaClient({"success": True, "action": "other", "score": 0.9}))

    with pytest.raises(AuthenticationError, match="action mismatch"):
        await verifier.verify("token-x")


async def test_recaptcha_hostname_mismatch():
    verifier = RecaptchaVerifier(_verifier(hostnames=("admin.example.com",)), StaticRecaptchaClient({"success": True, "action": "admin_login", "score": 0.9, "hostname": "evil.com"}))

    with pytest.raises(AuthenticationError, match="hostname mismatch"):
        await verifier.verify("token-x")


async def test_recaptcha_low_score():
    verifier = RecaptchaVerifier(_verifier(score=0.7), StaticRecaptchaClient({"success": True, "action": "admin_login", "score": 0.2}))

    with pytest.raises(AuthenticationError, match="score too low"):
        await verifier.verify("token-x")


async def test_recaptcha_provider_unavailable():
    class BrokenClient:
        async def verify(self, token):
            raise RuntimeError("network down")

    verifier = RecaptchaVerifier(_verifier(), BrokenClient())

    with pytest.raises(AuthenticationError, match="unavailable"):
        await verifier.verify("token-x")
