import asyncio
import mimetypes
import time
from pathlib import Path
from urllib.parse import urlencode

from fastkit_core.errors.exceptions import FastKitError
from fastkit_storage.errors import OBJECT_NOT_FOUND
from fastkit_storage.paths import safe_key
from fastkit_storage.provider import (
    ObjectStat,
    PresignedUrl,
    StorageHealth,
    StorageStatus,
)
from fastkit_storage.signing import sign


def _content_type_for(key: str, declared: str | None = None) -> str | None:
    return declared or mimetypes.guess_type(key)[0]


class LocalStorageProvider:
    """Filesystem-backed storage with signed local URLs, safe for a single node."""

    def __init__(
        self,
        root: str,
        base_url: str = "/media",
        secret: str = "local-secret",
        clock=None,
    ):
        self._root = Path(root)
        self._base_url = base_url.rstrip("/")
        self._secret = secret
        self._clock = clock or (lambda: int(time.time()))
        self._root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        return self._root / safe_key(key)

    def _write(self, path: Path, data: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    async def put(
        self, key: str, data: bytes, content_type: str | None = None
    ) -> ObjectStat:
        path = self._path(key)
        await asyncio.to_thread(self._write, path, data)
        normalized = safe_key(key)

        return ObjectStat(
            key=normalized,
            size_bytes=len(data),
            content_type=_content_type_for(normalized, content_type),
        )

    async def get(self, key: str) -> bytes:
        path = self._path(key)

        if not path.exists():
            raise FastKitError(OBJECT_NOT_FOUND, message=f"object '{key}' not found")

        return await asyncio.to_thread(path.read_bytes)

    async def delete(self, key: str) -> None:
        await asyncio.to_thread(self._path(key).unlink, True)

    async def exists(self, key: str) -> bool:
        return self._path(key).exists()

    async def stat(self, key: str) -> ObjectStat:
        path = self._path(key)

        if not path.exists():
            raise FastKitError(OBJECT_NOT_FOUND, message=f"object '{key}' not found")

        normalized = safe_key(key)

        return ObjectStat(
            key=normalized,
            size_bytes=path.stat().st_size,
            content_type=_content_type_for(normalized),
        )

    async def copy(self, source: str, destination: str) -> None:
        data = await self.get(source)
        await self.put(destination, data, _content_type_for(safe_key(source)))

    async def move(self, source: str, destination: str) -> None:
        await self.copy(source, destination)
        await self.delete(source)

    def _presign(self, key: str, expires_in: int, method: str) -> PresignedUrl:
        normalized = safe_key(key)
        expires_at = self._clock() + expires_in
        signature = sign(self._secret, normalized, expires_at, method)
        query = urlencode({"expires": expires_at, "signature": signature})

        return PresignedUrl(
            url=f"{self._base_url}/{normalized}?{query}",
            method=method,
            expires_in=expires_in,
        )

    async def presign_upload(self, key: str, expires_in: int = 3600) -> PresignedUrl:
        return self._presign(key, expires_in, "PUT")

    async def presign_download(self, key: str, expires_in: int = 3600) -> PresignedUrl:
        return self._presign(key, expires_in, "GET")

    async def health(self) -> StorageHealth:
        try:
            probe = self._root / ".health"
            await asyncio.to_thread(probe.write_bytes, b"1")
            await asyncio.to_thread(probe.unlink, True)

            return StorageHealth(StorageStatus.healthy)
        except OSError as error:
            return StorageHealth(StorageStatus.unavailable, detail=str(error))
