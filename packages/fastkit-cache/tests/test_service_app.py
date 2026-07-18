import pytest
import pytest_asyncio

from fastkit_core.app_config import CoreApp
from fastkit_core.runtime import Runtime
from fastkit_db.app import DbApp
from fastkit_cache.app import CacheApp, build_provider
from fastkit_cache.database import CacheEntry, DatabaseCacheProvider
from fastkit_cache.file import FileCacheProvider
from fastkit_cache.service import Cache


async def test_cache_facade_roundtrip(tmp_path, clock):
    provider = FileCacheProvider(str(tmp_path / "cache"), clock=clock)
    cache = Cache(provider, environment="dev", default_ttl=100)

    await cache.set("users", "1", {"name": "Ada"}, tenant_id=5)

    assert await cache.get("users", "1", tenant_id=5) == {"name": "Ada"}
    assert await cache.get("users", "missing") is None
    assert (await cache.health()).status.value == "healthy"

    await cache.delete("users", "1", tenant_id=5)
    assert await cache.get("users", "1", tenant_id=5) is None

    await cache.set("posts", "a", 1)
    await cache.clear_namespace("posts")
    assert await cache.get("posts", "a") is None


class Settings:
    class app:
        environment = "dev"

    class database:
        url = "sqlite+aiosqlite:///:memory:"
        pool_pre_ping = True
        echo = False

    class cache:
        provider = "file"
        default_ttl_seconds = 300
        directory = ""

    installed_apps = ["fastkit.core", "fastkit.db", "fastkit.cache"]


@pytest_asyncio.fixture
async def runtime(monkeypatch, tmp_path):
    monkeypatch.setattr("fastkit_core.runtime.discover_apps", lambda: {"fastkit.core": CoreApp, "fastkit.db": DbApp, "fastkit.cache": CacheApp})

    settings = Settings()
    settings.cache.directory = str(tmp_path / "cache")

    runtime = Runtime(settings=settings, installed_apps=list(settings.installed_apps))
    runtime.bootstrap()

    yield runtime

    await runtime.stop()


async def test_cache_app_registers_and_health(runtime):
    assert isinstance(runtime.component("cache"), Cache)
    assert CacheEntry in runtime.models.all()

    report = await runtime.health.run()
    assert report.status.value in ("healthy", "degraded")


def _settings(provider, tmp_path):
    settings = Settings()
    settings.cache.provider = provider
    settings.cache.directory = str(tmp_path)

    return settings


class FakeContext:
    def __init__(self, database):
        self._database = database

    def component(self, name):
        return self._database


def test_build_provider_file(tmp_path):
    provider = build_provider(_settings("file", tmp_path), FakeContext(None))

    assert isinstance(provider, FileCacheProvider)


def test_build_provider_database(tmp_path, database):
    provider = build_provider(_settings("database", tmp_path), FakeContext(database))

    assert isinstance(provider, DatabaseCacheProvider)


def test_build_provider_unknown(tmp_path):
    with pytest.raises(ValueError, match="unknown cache provider"):
        build_provider(_settings("memcached", tmp_path), FakeContext(None))
