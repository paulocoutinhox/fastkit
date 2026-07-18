from dataclasses import dataclass

from fastkit_cache.provider.status import CacheStatus


@dataclass(frozen=True)
class CacheHealth:
    status: CacheStatus
    detail: str | None = None
