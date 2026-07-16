import logging

from fastkit_core.resilience import CircuitBreaker, CircuitState
from fastkit_cache.provider import CacheHealth, CacheStatus

logger = logging.getLogger("fastkit.cache")


class RedisCacheProvider:
    """Redis provider that degrades gracefully behind a circuit breaker instead of crashing."""

    def __init__(self, client, breaker: CircuitBreaker | None = None):
        self._client = client
        self._breaker = breaker or CircuitBreaker(failure_threshold=3)

    async def _guard(self, coro_factory, fallback):
        if not self._breaker.allow():
            return fallback

        try:
            result = await coro_factory()
            self._breaker.record_success()

            return result
        except Exception:
            self._breaker.record_failure()
            logger.warning("redis cache operation failed, serving degraded", exc_info=True)

            return fallback

    async def get(self, key: str) -> bytes | None:
        return await self._guard(lambda: self._client.get(key), None)

    async def set(self, key: str, value: bytes, ttl: int | None = None) -> None:
        await self._guard(lambda: self._client.set(key, value, ex=ttl), None)

    async def delete(self, key: str) -> None:
        await self._guard(lambda: self._client.delete(key), None)

    async def delete_many(self, keys: list[str]) -> None:
        if keys:
            await self._guard(lambda: self._client.delete(*keys), None)

    async def exists(self, key: str) -> bool:
        return bool(await self._guard(lambda: self._client.exists(key), 0))

    async def touch(self, key: str, ttl: int) -> None:
        await self._guard(lambda: self._client.expire(key, ttl), None)

    async def increment(self, key: str, amount: int = 1) -> int:
        return int(await self._guard(lambda: self._client.incrby(key, amount), 0))

    async def clear_namespace(self, namespace: str) -> None:
        await self._guard(lambda: self._clear(namespace), None)

    async def _clear(self, namespace: str) -> None:
        marker = f":{namespace}:"
        keys = [key async for key in self._client.scan_iter(match=f"*{marker}*")]

        if keys:
            await self._client.delete(*keys)

    async def health(self) -> CacheHealth:
        if self._breaker.state is CircuitState.open:
            return CacheHealth(CacheStatus.degraded, detail="circuit open")

        try:
            await self._client.ping()

            return CacheHealth(CacheStatus.healthy)
        except Exception as error:
            return CacheHealth(CacheStatus.unavailable, detail=str(error))
