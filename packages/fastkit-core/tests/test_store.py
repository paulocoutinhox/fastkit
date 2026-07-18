from fastkit_core.store import MemoryKeyValueStore, SharedKeyValueStore


async def test_memory_store_get_set_delete_and_ttl():
    now = {"value": 0.0}
    store = MemoryKeyValueStore(clock=lambda: now["value"])

    assert await store.get("k") is None

    await store.set("k", b"v", ttl=10)
    assert await store.get("k") == b"v"

    now["value"] = 20.0
    assert await store.get("k") is None

    await store.set("p", b"persist")
    now["value"] = 10_000.0
    assert await store.get("p") == b"persist"

    await store.set("d", b"x")
    await store.delete("d")
    assert await store.get("d") is None


async def test_memory_store_increment_creates_expires_and_accumulates():
    now = {"value": 0.0}
    store = MemoryKeyValueStore(clock=lambda: now["value"])

    assert await store.increment("c", ttl=10) == 1
    assert await store.increment("c", amount=2) == 3
    assert await store.get("c") == b"3"

    now["value"] = 20.0
    assert await store.increment("c") == 1


async def test_shared_store_delegates_to_the_resolved_provider():
    backing = MemoryKeyValueStore()
    store = SharedKeyValueStore(lambda: backing)

    await store.set("k", b"v", ttl=5)
    assert await store.get("k") == b"v"
    assert await store.increment("n") == 1

    await store.delete("k")
    assert await store.get("k") is None
