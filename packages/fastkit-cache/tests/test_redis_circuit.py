
from fastkit_core.resilience import CircuitBreaker, CircuitState
from fastkit_cache.provider import CacheStatus
from fastkit_cache.redis import RedisCacheProvider


class StepClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def test_circuit_breaker_opens_and_recovers():
    clock = StepClock()
    breaker = CircuitBreaker(failure_threshold=2, reset_after_seconds=10, clock=clock)

    assert breaker.allow()
    breaker.record_failure()
    breaker.record_failure()

    assert breaker.state is CircuitState.open
    assert not breaker.allow()

    clock.now = 15
    assert breaker.allow()
    assert breaker.state is CircuitState.half_open

    breaker.record_success()
    assert breaker.state is CircuitState.closed


async def test_redis_provider_contract(fake_redis_cls):
    provider = RedisCacheProvider(fake_redis_cls())

    await provider.set("fastkit:dev:global:1:users:a", b"value", ttl=100)
    assert await provider.get("fastkit:dev:global:1:users:a") == b"value"
    assert await provider.exists("fastkit:dev:global:1:users:a")

    await provider.touch("fastkit:dev:global:1:users:a", ttl=10)
    assert await provider.increment("fastkit:dev:global:1:counter:c") == 1

    await provider.set("fastkit:dev:global:1:posts:b", b"2")
    await provider.clear_namespace("posts")
    assert await provider.get("fastkit:dev:global:1:posts:b") is None
    await provider.clear_namespace("nothing-matches")

    await provider.delete("fastkit:dev:global:1:users:a")
    await provider.delete_many([])
    await provider.delete_many(["x"])


async def test_redis_provider_degrades_when_down(fake_redis_cls):
    breaker = CircuitBreaker(failure_threshold=2)
    provider = RedisCacheProvider(fake_redis_cls(fail=True), breaker=breaker)

    assert await provider.get("k") is None
    assert await provider.get("k") is None
    assert not await provider.exists("k")

    assert breaker.state is CircuitState.open
    assert await provider.get("k") is None


async def test_redis_health_states(fake_redis_cls):
    healthy = RedisCacheProvider(fake_redis_cls())
    assert (await healthy.health()).status is CacheStatus.healthy

    unavailable = RedisCacheProvider(fake_redis_cls(fail=True))
    assert (await unavailable.health()).status is CacheStatus.unavailable


async def test_redis_health_degraded_when_open(fake_redis_cls):
    breaker = CircuitBreaker(failure_threshold=1)
    provider = RedisCacheProvider(fake_redis_cls(fail=True), breaker=breaker)

    await provider.get("k")

    assert (await provider.health()).status is CacheStatus.degraded
