import pytest_asyncio

from fastkit_core.app_config import CoreApp
from fastkit_core.runtime import Runtime
from fastkit_db.app import DbApp
from fastkit_tenancy.app import TenancyApp
from fastkit_tenancy.models import Tenant
from fastkit_tenancy.service import TenantService


class Settings:
    class database:
        url = "sqlite+aiosqlite:///:memory:"
        pool_pre_ping = True
        echo = False

    installed_apps = ["fastkit.core", "fastkit.db", "fastkit.tenancy"]


@pytest_asyncio.fixture
async def runtime(monkeypatch):
    monkeypatch.setattr(
        "fastkit_core.runtime.discover_apps",
        lambda: {"fastkit.core": CoreApp, "fastkit.db": DbApp, "fastkit.tenancy": TenancyApp},
    )
    runtime = Runtime(settings=Settings(), installed_apps=list(Settings.installed_apps))
    runtime.bootstrap()

    yield runtime

    await runtime.stop()


async def test_tenancy_app_registers_model_and_service(runtime):
    assert Tenant in runtime.models.all()
    assert isinstance(runtime.component("tenant_service"), TenantService)
