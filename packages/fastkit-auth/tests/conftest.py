from datetime import datetime, timezone

import pytest
import pytest_asyncio

from fastkit_db.base import Base
from fastkit_db.engine import Database

from fastkit_accounts import models as account_models  # noqa: F401
from fastkit_accounts.service import AccountService
from fastkit_auth import models as auth_models  # noqa: F401
from fastkit_auth.passwords import PasswordHashService
from fastkit_auth.ratelimit import RateLimiter
from fastkit_auth.recaptcha import RecaptchaConfig, RecaptchaVerifier, StaticRecaptchaClient
from fastkit_auth.service import AuthService
from fastkit_auth.sessions import SessionService
from fastkit_auth.tokens import TokenService


class Clock:
    def __init__(self):
        self.now = datetime(2026, 7, 14, 12, 0, 0, tzinfo=timezone.utc)

    def __call__(self):
        return self.now

    def advance(self, seconds):
        from datetime import timedelta

        self.now += timedelta(seconds=seconds)


@pytest_asyncio.fixture
async def database(tmp_path):
    db = Database(url=f"sqlite+aiosqlite:///{tmp_path}/auth.db")
    await db.create_all(Base.metadata)

    yield db

    await db.dispose()


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def passwords():
    return PasswordHashService(min_length=12)


@pytest.fixture
def accounts(database):
    return AccountService(database.session_factory)


@pytest.fixture
def recaptcha_disabled():
    config = RecaptchaConfig(enabled=False, action="admin_login", minimum_score=0.5, allowed_hostnames=())

    return RecaptchaVerifier(config, StaticRecaptchaClient({"success": True}))


@pytest.fixture
def session_service(database, clock):
    return SessionService(database.session_factory, ttl_seconds=100, clock=clock)


@pytest.fixture
def auth_service(database, accounts, passwords, clock, recaptcha_disabled):
    sessions = SessionService(database.session_factory, ttl_seconds=3600, clock=clock)
    tokens = TokenService(secret_key="test-secret", ttl_seconds=3600)
    limiter = RateLimiter(max_attempts=5, window_seconds=60, clock=lambda: 0.0)

    return AuthService(
        database.session_factory,
        accounts,
        passwords,
        sessions,
        tokens,
        limiter,
        recaptcha_disabled,
        max_failed=3,
        lockout_seconds=900,
        clock=clock,
    )
