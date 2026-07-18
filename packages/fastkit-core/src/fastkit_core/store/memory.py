import asyncio
import time


class MemoryKeyValueStore:
    """In-process key-value store with TTL and an atomic counter, for a single-worker deployment."""

    def __init__(self, clock=None):
        self._clock = clock or time.monotonic
        self._entries: dict[str, tuple[bytes, float | None]] = {}
        self._lock = asyncio.Lock()

    def _live(self, key: str) -> tuple[bytes, float | None] | None:
        entry = self._entries.get(key)

        if entry is None:
            return None

        if entry[1] is not None and entry[1] <= self._clock():
            del self._entries[key]

            return None

        return entry

    async def get(self, key: str) -> bytes | None:
        entry = self._live(key)

        return entry[0] if entry is not None else None

    async def set(self, key: str, value: bytes, ttl: int | None = None) -> None:
        expires_at = self._clock() + ttl if ttl is not None else None
        self._entries[key] = (value, expires_at)

    async def delete(self, key: str) -> None:
        self._entries.pop(key, None)

    async def increment(self, key: str, amount: int = 1, ttl: int | None = None) -> int:
        async with self._lock:
            entry = self._live(key)

            if entry is None:
                value = amount
                expires_at = self._clock() + ttl if ttl is not None else None
            else:
                value = int(entry[0].decode("utf-8")) + amount
                expires_at = entry[1]

            self._entries[key] = (str(value).encode("utf-8"), expires_at)

            return value
