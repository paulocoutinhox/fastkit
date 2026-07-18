import pytest
import pytest_asyncio

from fastkit_db.base import Base
from fastkit_db.engine import Database

from fastkit_content import models  # noqa: F401
from fastkit_content.service import ContentService, LanguageService


@pytest_asyncio.fixture
async def database(tmp_path):
    db = Database(url=f"sqlite+aiosqlite:///{tmp_path}/content.db")
    await db.create_all(Base.metadata)

    yield db

    await db.dispose()


@pytest.fixture
def languages(database):
    return LanguageService(database)


@pytest.fixture
def content(database):
    return ContentService(database)
