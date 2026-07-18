import asyncio
import os
import struct
import time
from pathlib import Path

from fastkit_cache.namespaces import hash_key
from fastkit_cache.provider import CacheHealth, CacheStatus

_HEADER = struct.Struct("<dI")


class FileCacheProvider:
    """Single-node file cache with atomic writes, TTL and namespace-aware clearing."""

    def __init__(self, root: str, clock=None):
        self._root = Path(root)
        self._clock = clock or time.time
        self._root.mkdir(parents=True, exist_ok=True)

    def _path_for(self, key: str) -> Path:
        digest = hash_key(key)

        return self._root / digest[:2] / digest[2:4] / digest

    def _encode(self, key: str, value: bytes, ttl: int | None) -> bytes:
        expires_at = self._clock() + ttl if ttl is not None else 0.0
        key_bytes = key.encode("utf-8")

        return _HEADER.pack(expires_at, len(key_bytes)) + key_bytes + value

    def _decode(self, raw: bytes) -> tuple[float, str, bytes]:
        expires_at, key_len = _HEADER.unpack_from(raw)
        offset = _HEADER.size
        key = raw[offset : offset + key_len].decode("utf-8")

        return expires_at, key, raw[offset + key_len :]

    def _write_sync(self, path: Path, payload: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(".tmp")
        temp.write_bytes(payload)
        os.replace(temp, path)

    def _read_valid(self, path: Path) -> bytes | None:
        if not path.exists():
            return None

        expires_at, _, value = self._decode(path.read_bytes())

        if expires_at and expires_at <= self._clock():
            path.unlink(missing_ok=True)

            return None

        return value

    async def get(self, key: str) -> bytes | None:
        return await asyncio.to_thread(self._read_valid, self._path_for(key))

    async def set(self, key: str, value: bytes, ttl: int | None = None) -> None:
        await asyncio.to_thread(
            self._write_sync, self._path_for(key), self._encode(key, value, ttl)
        )

    async def delete(self, key: str) -> None:
        await asyncio.to_thread(self._path_for(key).unlink, True)

    async def delete_many(self, keys: list[str]) -> None:
        for key in keys:
            await self.delete(key)

    async def exists(self, key: str) -> bool:
        return await self.get(key) is not None

    async def touch(self, key: str, ttl: int) -> None:
        value = await self.get(key)

        if value is not None:
            await self.set(key, value, ttl)

    async def increment(self, key: str, amount: int = 1) -> int:
        current = await self.get(key)
        value = int(current.decode("utf-8")) if current is not None else 0
        value += amount

        await self.set(key, str(value).encode("utf-8"))

        return value

    async def clear_namespace(self, namespace: str) -> None:
        await asyncio.to_thread(self._clear_namespace_sync, namespace)

    def _clear_namespace_sync(self, namespace: str) -> None:
        marker = f":{namespace}:"

        for path in self._root.rglob("*"):
            if not path.is_file() or path.suffix == ".tmp":
                continue

            _, key, _ = self._decode(path.read_bytes())

            if marker in key:
                path.unlink(missing_ok=True)

    async def health(self) -> CacheHealth:
        try:
            probe = self._root / ".health"
            await asyncio.to_thread(probe.write_bytes, b"1")
            await asyncio.to_thread(probe.unlink, True)

            return CacheHealth(CacheStatus.healthy)
        except OSError as error:
            return CacheHealth(CacheStatus.unavailable, detail=str(error))
