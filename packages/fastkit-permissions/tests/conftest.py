import pytest_asyncio

from fastkit_db.base import Base
from fastkit_db.engine import Database

from fastkit_accounts import models as account_models  # noqa: F401
from fastkit_accounts.service import AccountService
from fastkit_permissions import models  # noqa: F401
from fastkit_permissions.authorization import Authorizer
from fastkit_permissions.cache import PermissionCache
from fastkit_permissions.service import PermissionService


@pytest_asyncio.fixture
async def database(tmp_path):
    db = Database(url=f"sqlite+aiosqlite:///{tmp_path}/perm.db")
    await db.create_all(Base.metadata)

    yield db

    await db.dispose()


@pytest_asyncio.fixture
def cache():
    return PermissionCache()


@pytest_asyncio.fixture
def service(database, cache):
    return PermissionService(database, cache)


@pytest_asyncio.fixture
def authorizer(service, cache):
    return Authorizer(service, cache)


@pytest_asyncio.fixture
def accounts(database):
    return AccountService(database)
