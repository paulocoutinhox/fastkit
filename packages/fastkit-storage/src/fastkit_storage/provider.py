from dataclasses import dataclass
from enum import Enum
from typing import Protocol


class StorageStatus(str, Enum):
    healthy = "healthy"
    unavailable = "unavailable"


@dataclass(frozen=True)
class StorageHealth:
    status: StorageStatus
    detail: str | None = None


@dataclass(frozen=True)
class ObjectStat:
    key: str
    size_bytes: int
    content_type: str | None


@dataclass(frozen=True)
class PresignedUrl:
    url: str
    method: str
    expires_in: int


class StorageProvider(Protocol):
    async def put(self, key: str, data: bytes, content_type: str | None = None) -> ObjectStat:
        ...

    async def get(self, key: str) -> bytes:
        ...

    async def delete(self, key: str) -> None:
        ...

    async def exists(self, key: str) -> bool:
        ...

    async def stat(self, key: str) -> ObjectStat:
        ...

    async def copy(self, source: str, destination: str) -> None:
        ...

    async def move(self, source: str, destination: str) -> None:
        ...

    async def presign_upload(self, key: str, expires_in: int = 3600) -> PresignedUrl:
        ...

    async def presign_download(self, key: str, expires_in: int = 3600) -> PresignedUrl:
        ...

    async def health(self) -> StorageHealth:
        ...
