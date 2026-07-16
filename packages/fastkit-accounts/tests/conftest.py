import pytest_asyncio

from fastkit_db.base import Base
from fastkit_db.engine import Database

from fastkit_accounts import models  # noqa: F401
from fastkit_accounts.service import AccountService


@pytest_asyncio.fixture
async def database(tmp_path):
    db = Database(url=f"sqlite+aiosqlite:///{tmp_path}/accounts.db")
    await db.create_all(Base.metadata)

    yield db

    await db.dispose()


@pytest_asyncio.fixture
def service(database):
    return AccountService(database.session_factory)
