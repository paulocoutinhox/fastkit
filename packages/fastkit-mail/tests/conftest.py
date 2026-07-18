from datetime import datetime, timezone
from pathlib import Path

import pytest
import pytest_asyncio

from fastkit_db.base import Base
from fastkit_db.engine import Database

from fastkit_mail import models  # noqa: F401
from fastkit_mail.memory import MemoryEmailProvider
from fastkit_mail.service import MailService
from fastkit_mail.templates import MailTemplateRenderer

PACKAGE_TEMPLATES = str(Path(__file__).resolve().parents[1] / "src" / "fastkit_mail" / "templates")


class Clock:
    def __init__(self):
        self.now = datetime(2026, 7, 14, 12, 0, 0, tzinfo=timezone.utc)

    def __call__(self):
        return self.now


@pytest_asyncio.fixture
async def database(tmp_path):
    db = Database(url=f"sqlite+aiosqlite:///{tmp_path}/mail.db")
    await db.create_all(Base.metadata)

    yield db

    await db.dispose()


@pytest.fixture
def package_templates():
    return PACKAGE_TEMPLATES


@pytest.fixture
def renderer(package_templates):
    return MailTemplateRenderer(search_dirs=[package_templates])


@pytest.fixture
def provider():
    return MemoryEmailProvider()


@pytest.fixture
def service(database, renderer, provider):
    return MailService(database, renderer, provider, "memory", "no-reply@fastkit.local", clock=Clock())
