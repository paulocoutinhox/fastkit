import pytest_asyncio

from fastkit_core.app_config import CoreApp
from fastkit_core.runtime import Runtime
from fastkit_db.app import DbApp
from fastkit_tenancy.app import TenancyApp
from fastkit_accounts.app import AccountsApp
from fastkit_permissions.app import PermissionsApp
from fastkit_permissions.authorization import Authorizer
from fastkit_permissions.models import Permission


class Settings:
    class database:
        url = "sqlite+aiosqlite:///:memory:"
        pool_pre_ping = True
        echo = False

    installed_apps = [
        "fastkit.core",
        "fastkit.db",
        "fastkit.tenancy",
        "fastkit.accounts",
        "fastkit.permissions",
    ]


@pytest_asyncio.fixture
async def runtime(monkeypatch):
    monkeypatch.setattr(
        "fastkit_core.runtime.discover_apps",
        lambda: {
            "fastkit.core": CoreApp,
            "fastkit.db": DbApp,
            "fastkit.tenancy": TenancyApp,
            "fastkit.accounts": AccountsApp,
            "fastkit.permissions": PermissionsApp,
        },
    )
    runtime = Runtime(settings=Settings(), installed_apps=list(Settings.installed_apps))
    runtime.bootstrap()

    yield runtime

    await runtime.stop()


async def test_permissions_app_registers(runtime):
    assert Permission in runtime.models.all()
    assert isinstance(runtime.component("authorizer"), Authorizer)
    assert runtime.component("permission_cache") is not None
    assert runtime.component("permission_service") is not None
