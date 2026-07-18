import pytest_asyncio

from fastkit_core.app_config import CoreApp
from fastkit_core.runtime import Runtime
from fastkit_db.app import DbApp
from fastkit_tenancy.app import TenancyApp
from fastkit_accounts.app import AccountsApp
from fastkit_accounts.models import User
from fastkit_accounts.service import AccountService


class Settings:
    class database:
        url = "sqlite+aiosqlite:///:memory:"
        pool_pre_ping = True
        pool_recycle = 1800
        echo = False

    installed_apps = [
        "fastkit.core",
        "fastkit.db",
        "fastkit.tenancy",
        "fastkit.accounts",
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
        },
    )
    runtime = Runtime(settings=Settings(), installed_apps=list(Settings.installed_apps))
    runtime.bootstrap()

    yield runtime

    await runtime.stop()


async def test_accounts_app_registers(runtime):
    assert User in runtime.models.all()
    assert isinstance(runtime.component("account_service"), AccountService)
    assert runtime.component("normalizer_registry").get("email").type == "email"
