import pytest
import pytest_asyncio

from fastkit_db.base import Base
from fastkit_db.engine import Database

from fastkit_cache import database as cache_database  # noqa: F401


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class FakeRedis:
    """Minimal in-memory async stand-in for redis.asyncio.Redis used in tests."""

    def __init__(self, fail=False):
        self.store: dict[str, bytes] = {}
        self.fail = fail

    def _check(self):
        if self.fail:
            raise ConnectionError("redis down")

    async def get(self, key):
        self._check()

        return self.store.get(key)

    async def set(self, key, value, ex=None):
        self._check()
        self.store[key] = value

    async def delete(self, *keys):
        self._check()

        for key in keys:
            self.store.pop(key, None)

    async def exists(self, key):
        self._check()

        return 1 if key in self.store else 0

    async def expire(self, key, ttl):
        self._check()

    async def incrby(self, key, amount):
        self._check()
        value = int(self.store.get(key, b"0")) + amount
        self.store[key] = str(value).encode("utf-8")

        return value

    async def scan_iter(self, match=None):
        self._check()
        marker = match.strip("*") if match else ""

        for key in list(self.store):
            if marker in key:
                yield key

    async def ping(self):
        self._check()

        return True


@pytest.fixture
def clock():
    return FakeClock()


@pytest.fixture
def fake_redis_cls():
    return FakeRedis


@pytest_asyncio.fixture
async def database(tmp_path):
    db = Database(url=f"sqlite+aiosqlite:///{tmp_path}/cache.db")
    await db.create_all(Base.metadata)

    yield db

    await db.dispose()
