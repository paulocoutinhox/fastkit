from typing import Protocol


class KeyValueStore(Protocol):
    """Byte key-value store with TTL and an atomic counter.

    The single async seam every cross-cutting stateful concern (rate limiting, captcha challenges,
    the permission cache, ...) depends on instead of a concrete backend. A single-worker deployment
    uses `MemoryKeyValueStore`, a multi-worker one uses `SharedKeyValueStore` over the cache provider.
    """

    async def get(self, key: str) -> bytes | None: ...

    async def set(self, key: str, value: bytes, ttl: int | None = None) -> None: ...

    async def delete(self, key: str) -> None: ...

    async def increment(
        self, key: str, amount: int = 1, ttl: int | None = None
    ) -> int: ...
