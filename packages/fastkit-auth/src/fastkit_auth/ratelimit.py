from collections import defaultdict

from fastkit_core.errors.exceptions import RateLimitError
from fastkit_auth.errors import RATE_LIMITED


class RateLimiter:
    """Fixed-window in-memory rate limiter keyed by IP, tenant and identifier."""

    def __init__(self, max_attempts: int, window_seconds: int, clock=None):
        self._max_attempts = max_attempts
        self._window_seconds = window_seconds
        self._clock = clock or _default_clock
        self._buckets: dict[str, list[float]] = defaultdict(list)

    def hit(self, *parts) -> None:
        key = ":".join(str(part) for part in parts)
        now = self._clock()

        recent = [stamp for stamp in self._buckets[key] if now - stamp < self._window_seconds]

        if len(recent) >= self._max_attempts:
            self._buckets[key] = recent
            raise RateLimitError(RATE_LIMITED, message="too many attempts, please try again later")

        recent.append(now)
        self._buckets[key] = recent

    def reset(self, *parts) -> None:
        key = ":".join(str(part) for part in parts)
        self._buckets.pop(key, None)


def _default_clock() -> float:
    import time

    return time.monotonic()
