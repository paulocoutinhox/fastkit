from datetime import datetime, timezone


from fastkit_cache.database import DatabaseCacheProvider, _namespace_of
from fastkit_cache.file import FileCacheProvider
from fastkit_cache.namespaces import build_key, hash_key


class DatetimeClock:
    def __init__(self):
        self.now = datetime(2026, 7, 14, 12, 0, 0, tzinfo=timezone.utc)

    def __call__(self):
        return self.now

    def advance(self, seconds):
        from datetime import timedelta

        self.now += timedelta(seconds=seconds)


def test_build_key_and_hash():
    key = build_key("prod", 5, 2, "users", "abc")
    assert key == "fastkit:prod:5:2:users:abc"
    assert build_key("prod", None, 1, "ns", "k").split(":")[2] == "global"
    assert hash_key("x") == hash_key("x")


def test_namespace_extraction():
    assert _namespace_of("fastkit:dev:global:1:users:abc") == "users"
    assert _namespace_of("short:key") == "default"


async def test_file_provider_full_contract(tmp_path, clock):
    provider = FileCacheProvider(str(tmp_path / "cache"), clock=clock)

    await provider.set("fastkit:dev:global:1:users:a", b"value", ttl=100)
    assert await provider.get("fastkit:dev:global:1:users:a") == b"value"
    assert await provider.exists("fastkit:dev:global:1:users:a")
    assert await provider.get("missing") is None

    await provider.touch("fastkit:dev:global:1:users:a", ttl=200)
    await provider.touch("missing", ttl=10)

    assert await provider.increment("fastkit:dev:global:1:counter:c") == 1
    assert await provider.increment("fastkit:dev:global:1:counter:c", 4) == 5

    await provider.delete("fastkit:dev:global:1:users:a")
    assert await provider.get("fastkit:dev:global:1:users:a") is None
    await provider.delete_many(["missing1", "missing2"])


async def test_file_provider_ttl_expiry(tmp_path, clock):
    provider = FileCacheProvider(str(tmp_path / "cache"), clock=clock)
    await provider.set("fastkit:dev:global:1:users:a", b"value", ttl=10)

    clock.advance(20)

    assert await provider.get("fastkit:dev:global:1:users:a") is None


async def test_file_provider_no_ttl_persists(tmp_path, clock):
    provider = FileCacheProvider(str(tmp_path / "cache"), clock=clock)
    await provider.set("fastkit:dev:global:1:users:a", b"value")

    clock.advance(100000)

    assert await provider.get("fastkit:dev:global:1:users:a") == b"value"


async def test_file_provider_clear_namespace(tmp_path, clock):
    provider = FileCacheProvider(str(tmp_path / "cache"), clock=clock)
    await provider.set("fastkit:dev:global:1:users:a", b"1")
    await provider.set("fastkit:dev:global:1:posts:b", b"2")

    await provider.clear_namespace("users")

    assert await provider.get("fastkit:dev:global:1:users:a") is None
    assert await provider.get("fastkit:dev:global:1:posts:b") == b"2"


async def test_file_provider_health(tmp_path):
    provider = FileCacheProvider(str(tmp_path / "cache"))

    assert (await provider.health()).status.value == "healthy"


async def test_file_provider_health_unavailable(tmp_path, monkeypatch):
    provider = FileCacheProvider(str(tmp_path / "cache"))

    async def broken(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr("fastkit_cache.file.asyncio.to_thread", broken)

    assert (await provider.health()).status.value == "unavailable"


async def test_database_provider_full_contract(database):
    provider = DatabaseCacheProvider(database.session_factory, clock=DatetimeClock())

    await provider.set("fastkit:dev:global:1:users:a", b"value", ttl=100)
    assert await provider.get("fastkit:dev:global:1:users:a") == b"value"
    await provider.set("fastkit:dev:global:1:users:a", b"updated", ttl=100)
    assert await provider.get("fastkit:dev:global:1:users:a") == b"updated"

    assert await provider.exists("fastkit:dev:global:1:users:a")
    assert await provider.get("missing") is None

    await provider.touch("fastkit:dev:global:1:users:a", ttl=50)
    await provider.touch("missing", ttl=10)

    assert await provider.increment("fastkit:dev:global:1:counter:c") == 1
    assert await provider.increment("fastkit:dev:global:1:counter:c", 2) == 3

    await provider.delete("fastkit:dev:global:1:users:a")
    await provider.delete_many(["m1", "m2"])
    assert await provider.get("fastkit:dev:global:1:users:a") is None


async def test_database_provider_ttl_expiry(database):
    clock = DatetimeClock()
    provider = DatabaseCacheProvider(database.session_factory, clock=clock)
    await provider.set("fastkit:dev:global:1:users:a", b"value", ttl=10)

    clock.advance(20)

    assert await provider.get("fastkit:dev:global:1:users:a") is None


async def test_database_provider_clear_namespace(database):
    provider = DatabaseCacheProvider(database.session_factory, clock=DatetimeClock())
    await provider.set("fastkit:dev:global:1:users:a", b"1")
    await provider.set("fastkit:dev:global:1:posts:b", b"2")

    await provider.clear_namespace("users")

    assert await provider.get("fastkit:dev:global:1:users:a") is None
    assert await provider.get("fastkit:dev:global:1:posts:b") == b"2"


async def test_database_provider_health(database):
    provider = DatabaseCacheProvider(database.session_factory)

    assert (await provider.health()).status.value == "healthy"


async def test_database_provider_health_unavailable():
    def broken_factory():
        raise RuntimeError("db down")

    provider = DatabaseCacheProvider(broken_factory)

    assert (await provider.health()).status.value == "unavailable"


def test_aware_helper_keeps_tzaware():
    from fastkit_cache.database import _aware

    aware = datetime(2026, 1, 1, tzinfo=timezone.utc)

    assert _aware(aware) is aware
    assert _aware(datetime(2026, 1, 1)).tzinfo is timezone.utc
