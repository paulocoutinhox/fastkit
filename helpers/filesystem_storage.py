"""The directory of the machine this process runs on, which is what a developer reads with a file manager."""

from pathlib import Path
from shutil import copyfileobj
from typing import BinaryIO

from fastapi.concurrency import run_in_threadpool

from config.storage_settings import StorageSettings
from helpers.storage_contract import Storage

CHUNK = 1024 * 1024


class FilesystemStorage(Storage):
    def __init__(self, config: StorageSettings):
        self.root = config.root
        self.base_url = config.base_url.rstrip("/")

    def path_for(self, key: str) -> Path:
        """A key is a place under the root and never a way out of it, whatever a column of the database happens to hold."""
        wanted = (self.root / key).resolve()

        # The check is on the resolved path because `a/../../b` only shows what it is once it is resolved.
        if not wanted.is_relative_to(self.root.resolve()):
            raise ValueError(f"the key leaves the storage root: {key}")

        return wanted

    def write_file(self, key: str, data: bytes | BinaryIO) -> str:
        destination = self.path_for(key)
        destination.parent.mkdir(parents=True, exist_ok=True)

        if isinstance(data, bytes):
            destination.write_bytes(data)
        else:
            with destination.open("wb") as target:
                copyfileobj(data, target, CHUNK)

        return key

    def delete_file(self, key: str) -> None:
        target = self.path_for(key)

        if target.is_file():
            target.unlink()

    def list_files(self) -> list[str]:
        return [path.relative_to(self.root).as_posix() for path in sorted(self.root.rglob("*")) if path.is_file()]

    # The disk blocks, so every touch of it happens off the event loop.
    async def save(self, key: str, data: bytes | BinaryIO, content_type: str) -> str:
        return await run_in_threadpool(self.write_file, key, data)

    async def delete(self, key: str) -> None:
        await run_in_threadpool(self.delete_file, key)

    async def walk(self):
        for entry in await run_in_threadpool(self.list_files):
            yield entry
