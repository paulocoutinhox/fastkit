import pytest_asyncio

from fastkit_db.base import Base
from fastkit_db.engine import Database

from fastkit_tenancy import models  # noqa: F401


@pytest_asyncio.fixture
async def database(tmp_path):
    db = Database(url=f"sqlite+aiosqlite:///{tmp_path}/tenancy.db")
    await db.create_all(Base.metadata)

    yield db

    await db.dispose()
