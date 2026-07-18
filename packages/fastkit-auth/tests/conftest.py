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
from fastkit_auth.store import MemoryKeyValueStore
from fastkit_auth.captcha.disabled import DisabledCaptchaProvider
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
    return AccountService(database)


@pytest.fixture
def captcha_disabled():
    return DisabledCaptchaProvider()


@pytest.fixture
def session_service(database, clock):
    return SessionService(database, ttl_seconds=100, clock=clock)


@pytest.fixture
def auth_service(database, accounts, passwords, clock, captcha_disabled):
    sessions = SessionService(database, ttl_seconds=3600, clock=clock)
    tokens = TokenService(secret_key="test-secret", ttl_seconds=3600)
    limiter = RateLimiter(
        MemoryKeyValueStore(clock=lambda: 0.0),
        max_attempts=5,
        window_seconds=60,
        clock=lambda: 0.0,
    )

    return AuthService(
        database,
        accounts,
        passwords,
        sessions,
        tokens,
        limiter,
        captcha_disabled,
        max_failed=3,
        lockout_seconds=900,
        clock=clock,
    )
