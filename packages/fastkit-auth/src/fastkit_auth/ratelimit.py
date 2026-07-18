import hashlib
import time

from fastkit_core.errors.exceptions import RateLimitError
from fastkit_auth.errors import RATE_LIMITED


class RateLimiter:
    """Fixed-window rate limiter over a shared key-value store, keyed by IP, tenant and identifier.

    The counter lives in the store, so every worker in a multi-worker deployment shares one budget
    for a given key. The store's TTL rotates the window automatically.
    """

    def __init__(self, store, max_attempts: int, window_seconds: int, clock=None):
        self._store = store
        self._max_attempts = max_attempts
        self._window_seconds = window_seconds
        self._clock = clock or time.monotonic

    def _key(self, parts) -> str:
        raw = ":".join(str(part) for part in parts)
        window = int(self._clock()) // self._window_seconds
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()

        return f"auth:ratelimit:{digest}:{window}"

    async def hit(self, *parts) -> None:
        count = await self._store.increment(self._key(parts), ttl=self._window_seconds)

        if count > self._max_attempts:
            raise RateLimitError(
                RATE_LIMITED, message="too many attempts, please try again later"
            )

    async def reset(self, *parts) -> None:
        await self._store.delete(self._key(parts))
