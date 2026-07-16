from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio

from fastkit_db.base import Base
from fastkit_db.engine import Database

from fastkit_tasks import models  # noqa: F401
from fastkit_tasks.queue import TaskQueue
from fastkit_tasks.registry import TaskRegistry


class Clock:
    def __init__(self):
        self.now = datetime(2026, 7, 14, 12, 0, 0, tzinfo=timezone.utc)

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += timedelta(seconds=seconds)


@pytest_asyncio.fixture
async def database(tmp_path):
    db = Database(url=f"sqlite+aiosqlite:///{tmp_path}/tasks.db")
    await db.create_all(Base.metadata)

    yield db

    await db.dispose()


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def queue(database, clock):
    return TaskQueue(database.session_factory, clock=clock)


@pytest.fixture
def registry():
    return TaskRegistry()
