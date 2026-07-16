import os

import pytest

from fastkit_core.resilience import CircuitBreaker, CircuitState
from fastkit_cache.redis import RedisCacheProvider


async def test_real_client_degrades_on_connection_failure():
    """A real redis client pointed at a dead endpoint degrades instead of crashing."""

    pytest.importorskip("redis")
    from redis.asyncio import Redis

    client = Redis(host="127.0.0.1", port=6390, socket_connect_timeout=0.2, socket_timeout=0.2)
    breaker = CircuitBreaker(failure_threshold=1)
    provider = RedisCacheProvider(client, breaker=breaker)

    assert await provider.get("missing") is None
    assert not await provider.exists("missing")
    assert breaker.state is CircuitState.open

    await client.aclose()


async def test_real_client_reconnects_when_service_is_available():
    """When a real redis is reachable the provider talks to it and closes its circuit."""

    url = os.environ.get("FASTKIT_TEST_REDIS_URL")

    if not url:
        pytest.skip("set FASTKIT_TEST_REDIS_URL to run the redis integration test")

    pytest.importorskip("redis")
    from redis.asyncio import Redis

    client = Redis.from_url(url)
    provider = RedisCacheProvider(client)

    await provider.set("fastkit:probe", b"ok", ttl=5)

    assert await provider.get("fastkit:probe") == b"ok"

    await provider.delete("fastkit:probe")
    await client.aclose()
