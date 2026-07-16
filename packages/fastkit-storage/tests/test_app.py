import sys
import types

import pytest
import pytest_asyncio

from fastkit_core.app_config import CoreApp
from fastkit_core.runtime import Runtime
from fastkit_storage.app import StorageApp, build_provider
from fastkit_storage.local import LocalStorageProvider
from fastkit_storage.s3 import S3StorageProvider


class Settings:
    class app:
        environment = "dev"
        secret_key = "demo-secret"

    class storage:
        provider = "local"
        root = ""
        base_url = "/media"

    installed_apps = ["fastkit.core", "fastkit.storage"]


@pytest_asyncio.fixture
async def runtime(monkeypatch, tmp_path):
    monkeypatch.setattr("fastkit_core.runtime.discover_apps", lambda: {"fastkit.core": CoreApp, "fastkit.storage": StorageApp})

    settings = Settings()
    settings.storage.root = str(tmp_path / "media")

    runtime = Runtime(settings=settings, installed_apps=list(settings.installed_apps))
    runtime.bootstrap()

    yield runtime

    await runtime.stop()


async def test_storage_app_registers_and_health(runtime):
    assert isinstance(runtime.component("storage"), LocalStorageProvider)

    report = await runtime.health.run()
    assert report.status.value == "healthy"


def test_build_provider_local(tmp_path):
    settings = Settings()
    settings.storage.root = str(tmp_path)

    assert isinstance(build_provider(settings), LocalStorageProvider)


def test_build_provider_s3(monkeypatch, tmp_path):
    fake_module = types.ModuleType("aioboto3")

    class FakeSession:
        def client(self, name):
            return object()

    fake_module.Session = FakeSession
    monkeypatch.setitem(sys.modules, "aioboto3", fake_module)

    settings = Settings()
    settings.storage.provider = "s3"
    settings.storage.root = "my-bucket"

    assert isinstance(build_provider(settings), S3StorageProvider)


def test_build_provider_unknown():
    settings = Settings()
    settings.storage.provider = "ftp"

    with pytest.raises(ValueError, match="unknown storage provider"):
        build_provider(settings)
