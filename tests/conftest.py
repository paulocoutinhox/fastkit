import os
import socket
import tempfile
from pathlib import Path

WORKSPACE = Path(tempfile.mkdtemp(prefix="fastkit-tests-"))

os.environ["APP_ENV"] = "dev"

from helpers.settings import settings  # noqa: E402

# No config file reads the machine, so the suite points the engine at its own database before one is built.
settings.database.url = f"sqlite+aiosqlite:///{WORKSPACE / 'test.db'}"

# A form of the suite is answered by the code and not by a person, so the challenge the developer sees is off here.
settings.captcha.provider = "disabled"

# A product starts with one brand, so that is what dev serves, and the suite exercises the mode with more to go wrong.
# The other one is proven by tests/test_single_brand.py, which turns this back off for itself.
settings.multi_tenant = True

# Every test drops the schema, so pointing anywhere near the real database would wipe it.
assert str(WORKSPACE) in settings.database.url
assert "app.db" not in settings.database.url

import re  # noqa: E402

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from cachefy.store.sqlalchemy import metadata as cache_metadata  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from queuefy.store.sqlalchemy import metadata as task_metadata  # noqa: E402
from sqlalchemy import text  # noqa: E402

from enums.user import UserRole, UserStatus  # noqa: E402
from helpers import errors, head, headers, locale, payload, router, tracing  # noqa: E402
from helpers import site as site_helper  # noqa: E402
from helpers.db import AsyncSessionLocal, Base, async_engine  # noqa: E402
from helpers.schema import recreate_schema  # noqa: E402
from helpers.security import create_token  # noqa: E402
from helpers.storage import storage  # noqa: E402
from models.account import Currency  # noqa: E402
from models.country import Country  # noqa: E402
from models.tenant import Tenant  # noqa: E402
from models.user import User  # noqa: E402
from services.user import user_service  # noqa: E402

settings.storage.root = WORKSPACE / "media"
storage.root = settings.storage.root


def token_in(body: str) -> str:
    found = re.search(r'name="csrf_token" value="([^"]+)"', body)

    assert found, "the page drew a form with no token"

    return found.group(1)


async def opened(client, path: str) -> str:
    """What a browser does before it posts: it reads the page, and the cookie it keeps is what answers for the field."""
    return token_in((await client.get(path)).text)


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    """A gateway key that works is one a test can spend, so the suite never reaches a machine that is not this one."""

    def refuse(self, address):
        raise AssertionError(f"a test tried to reach {address}, and a gateway is answered by a stub and never by the network")

    monkeypatch.setattr(socket.socket, "connect", refuse)


built = []


@pytest_asyncio.fixture(autouse=True)
async def schema():
    """The shape is built once and emptied between tests, because rebuilding it for each of a thousand costs more than every test together."""
    import models.registry  # noqa: F401

    if not built:
        # The suite builds what the container builds, queue table and all, or a job could never be claimed here.
        await recreate_schema()
        built.append(True)

    yield

    async with async_engine.begin() as connection:
        await connection.execute(text("PRAGMA foreign_keys = OFF"))

        for table in reversed([*Base.metadata.sorted_tables, *task_metadata.sorted_tables, *cache_metadata.sorted_tables]):
            await connection.execute(table.delete())

        await connection.execute(text("PRAGMA foreign_keys = ON"))


@pytest_asyncio.fixture
async def db():
    async with AsyncSessionLocal() as session:
        yield session


@pytest.fixture
def app() -> FastAPI:
    application = FastAPI()

    locale.setup(application)
    head.setup(application)
    payload.setup(application)
    tracing.setup(application)
    headers.setup(application)
    errors.setup(application, site_helper.not_found, site_helper.broke)
    site_helper.setup(application)
    router.setup(application)
    router.setup_site(application)

    return application


@pytest_asyncio.fixture
async def site(app: FastAPI, tenant: Tenant):
    """The site answers by host, and the tenant of the suite is the one this address names."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=f"http://{tenant.domain}") as instance:
        yield instance


@pytest_asyncio.fixture
async def signed_in(site: AsyncClient, member: User):
    site.cookies.set(settings.site.session_cookie, create_token(member.token, member.role, member.session_epoch), domain=member.tenant.domain, path="/")

    return site


@pytest_asyncio.fixture
async def client(app: FastAPI):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as instance:
        yield instance


@pytest_asyncio.fixture
async def tenant(db) -> Tenant:
    record = Tenant(code="acme", name="Acme", domain="acme.test", meta={})

    db.add(record)
    await db.commit()

    return record


@pytest_asyncio.fixture
async def administrator(db) -> User:
    """The administrator is global on purpose, so deleting a tenant never takes the account that manages the others."""
    return await user_service.create(db, {"username": "root", "email": "root@acme.com", "password": "s3cret-password", "role": UserRole.ADMINISTRATOR, "status": UserStatus.ACTIVE})


@pytest_asyncio.fixture
async def member(db, tenant) -> User:
    return await user_service.create(db, {"username": "reader", "email": "reader@acme.com", "password": "s3cret-password", "role": UserRole.NORMAL, "status": UserStatus.ACTIVE, "tenant_id": tenant.id})


@pytest.fixture
def admin_headers(administrator: User) -> dict:
    return {"Authorization": f"Bearer {create_token(administrator.token, administrator.role, administrator.session_epoch)}"}


@pytest.fixture
def member_headers(member: User) -> dict:
    return {"Authorization": f"Bearer {create_token(member.token, member.role, member.session_epoch)}"}


@pytest.fixture
def tenant_headers(tenant: Tenant) -> dict:
    return {"X-Tenant-Code": tenant.code}


@pytest_asyncio.fixture
async def currency(db) -> Currency:
    """Every ledger names a currency now, so the suite has one the way it has a tenant."""
    row = Currency(code="coin", name="Coins", symbol="¢", meta={})

    db.add(row)
    await db.commit()

    return row


@pytest_asyncio.fixture
async def country(db) -> Country:
    """Every address names a country the registry offers now, so the suite has one the way it has a tenant."""
    row = Country(name="United Kingdom", code_iso_3166_1="GB")

    db.add(row)
    await db.commit()

    return row
