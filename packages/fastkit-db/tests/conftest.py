import pytest
import pytest_asyncio
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from fastkit_db.base import (
    ActiveFlagMixin,
    Base,
    MetadataMixin,
    SoftDeleteMixin,
    TenantMixin,
    TimestampMixin,
    PrimaryKeyMixin,
    VersionMixin,
)
from fastkit_db.engine import Database


class Widget(
    PrimaryKeyMixin,
    TimestampMixin,
    TenantMixin,
    SoftDeleteMixin,
    VersionMixin,
    MetadataMixin,
    ActiveFlagMixin,
    Base,
):
    __tablename__ = "widgets"

    name: Mapped[str] = mapped_column(String(120), nullable=False)


@pytest_asyncio.fixture
async def database(tmp_path):
    db = Database(url=f"sqlite+aiosqlite:///{tmp_path}/test.db")
    await db.create_all(Base.metadata)

    yield db

    await db.dispose()


@pytest_asyncio.fixture
async def session(database):
    async with database.session_factory() as active:
        yield active


@pytest.fixture
def widget():
    return Widget
