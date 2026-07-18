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


@pytest.fixture
def clock():
    return FakeClock()


@pytest_asyncio.fixture
async def database(tmp_path):
    db = Database(url=f"sqlite+aiosqlite:///{tmp_path}/cache.db")
    await db.create_all(Base.metadata)

    yield db

    await db.dispose()
