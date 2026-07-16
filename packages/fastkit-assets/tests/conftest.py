import io
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from PIL import Image

from fastkit_db.base import Base
from fastkit_db.engine import Database
from fastkit_storage.local import LocalStorageProvider

from fastkit_assets import models  # noqa: F401
from fastkit_assets.service import AssetService


def make_image(width=800, height=600, color=(120, 40, 200), fmt="PNG") -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), color).save(buffer, format=fmt)

    return buffer.getvalue()


class Clock:
    def __init__(self):
        self.now = datetime(2026, 7, 14, 12, 0, 0, tzinfo=timezone.utc)

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += timedelta(seconds=seconds)


@pytest_asyncio.fixture
async def database(tmp_path):
    db = Database(url=f"sqlite+aiosqlite:///{tmp_path}/assets.db")
    await db.create_all(Base.metadata)

    yield db

    await db.dispose()


@pytest.fixture
def storage(tmp_path):
    return LocalStorageProvider(str(tmp_path / "media"))


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def service(database, storage, clock):
    return AssetService(database.session_factory, storage, clock=clock)


@pytest.fixture
def image_factory():
    return make_image
