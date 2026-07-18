from dataclasses import dataclass
from enum import Enum
from typing import Protocol


class CacheStatus(str, Enum):
    healthy = "healthy"
    degraded = "degraded"
    unavailable = "unavailable"


@dataclass(frozen=True)
class CacheHealth:
    status: CacheStatus
    detail: str | None = None


class CacheProvider(Protocol):
    async def get(self, key: str) -> bytes | None: ...

    async def set(self, key: str, value: bytes, ttl: int | None = None) -> None: ...

    async def delete(self, key: str) -> None: ...

    async def delete_many(self, keys: list[str]) -> None: ...

    async def exists(self, key: str) -> bool: ...

    async def touch(self, key: str, ttl: int) -> None: ...

    async def increment(self, key: str, amount: int = 1) -> int: ...

    async def clear_namespace(self, namespace: str) -> None: ...

    async def health(self) -> CacheHealth: ...
