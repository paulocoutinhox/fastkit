"""Where a stored file lives, whichever machine actually holds it."""

import os
import re
import unicodedata
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from pathlib import Path
from shutil import copyfileobj
from typing import BinaryIO
from uuid import uuid4

import aioboto3
from fastapi.concurrency import run_in_threadpool

from config.base import StorageSettings
from enums.storage import StorageProvider
from enums.upload import Naming
from helpers.dates import now
from helpers.settings import settings

CHUNK = 1024 * 1024


# What is left of a name a person typed, which is the only part of it that ever reaches the storage.
UNSAFE = re.compile(r"[^a-z0-9]+")

# A name long enough to break a key is cut, because a bucket has a limit and nobody reads past this anyway.
NAME_LIMIT = 80


# Every stored file carries a UUID in its key, and that is the only thing a row ever mentions of it.
NAMED = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.IGNORECASE)


def uuids_in(value) -> set[str]:
    """Which stored files a value mentions, whether it is a key in a column of its own or a link inside the markup of a body."""
    return {found.group(0).lower() for found in NAMED.finditer(str(value))}


def readable_name(filename: str) -> str:
    """The name somebody uploaded, reduced to what a key may carry: no separator, no accent, no dot but the one before the extension."""
    stem = os.path.splitext(filename or "")[0]
    slug = UNSAFE.sub("-", unicodedata.normalize("NFKD", stem).encode("ascii", "ignore").decode().lower()).strip("-")

    return slug[:NAME_LIMIT] or "file"


def build_key(folder: str, filename: str, naming: Naming = Naming.UUID) -> str:
    """Every stored file carries a UUID, so two uploads never collide and the orphan sweep can always tell whose it is."""
    extension = os.path.splitext(filename or "")[1].lower()
    today = now()
    token = uuid4()

    # The UUID becomes a folder rather than the name, so the address ends in the name the person knows it by.
    if naming == Naming.ORIGINAL:
        return f"{folder}/{today:%Y/%m/%d}/{token}/{readable_name(filename)}{extension}"

    return f"{folder}/{today:%Y/%m/%d}/{token}{extension}"


class Storage(ABC):
    """Where a stored file lives, which is a directory of this machine or a bucket every copy of the process reaches."""

    @abstractmethod
    async def save(self, key: str, data: bytes | BinaryIO, content_type: str) -> str: ...

    @abstractmethod
    async def read(self, key: str) -> bytes | None: ...

    @abstractmethod
    async def delete(self, key: str) -> None: ...

    @abstractmethod
    def url(self, key: str) -> str: ...

    @abstractmethod
    def walk(self): ...


class FilesystemStorage(Storage):
    """The directory of the machine this process runs on, which is what a developer reads with a file manager."""

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

    def read_file(self, key: str) -> bytes | None:
        source = self.path_for(key)

        return source.read_bytes() if source.is_file() else None

    def delete_file(self, key: str) -> None:
        target = self.path_for(key)

        if target.is_file():
            target.unlink()

    def list_files(self) -> list[tuple[str, datetime]]:
        return [(path.relative_to(self.root).as_posix(), datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)) for path in sorted(self.root.rglob("*")) if path.is_file()]

    # The disk blocks, so every touch of it happens off the event loop.
    async def save(self, key: str, data: bytes | BinaryIO, content_type: str) -> str:
        return await run_in_threadpool(self.write_file, key, data)

    async def read(self, key: str) -> bytes | None:
        return await run_in_threadpool(self.read_file, key)

    async def delete(self, key: str) -> None:
        await run_in_threadpool(self.delete_file, key)

    def url(self, key: str) -> str:
        return f"{self.base_url}/{key}"

    async def walk(self):
        for entry in await run_in_threadpool(self.list_files):
            yield entry


class S3Storage(Storage):
    """Works against S3 and any compatible endpoint, which is how r2 is reached."""

    def __init__(self, config: StorageSettings):
        self.bucket = config.bucket
        self.base_url = config.base_url.rstrip("/")
        self.session = aioboto3.Session(aws_access_key_id=config.access_key, aws_secret_access_key=config.secret_key, region_name=config.region)
        self.client_options = {"endpoint_url": config.endpoint_url} if config.endpoint_url else {}

    async def save(self, key: str, data: bytes | BinaryIO, content_type: str) -> str:
        """Who may read an object is the bucket to say, and an upload that names an acl is refused by a bucket made today."""
        async with self.session.client("s3", **self.client_options) as client:
            await client.put_object(Bucket=self.bucket, Key=key, Body=data, ContentType=content_type)

        return key

    async def read(self, key: str) -> bytes | None:
        async with self.session.client("s3", **self.client_options) as client:
            try:
                response = await client.get_object(Bucket=self.bucket, Key=key)
            except client.exceptions.NoSuchKey:
                return None

            return await response["Body"].read()

    async def delete(self, key: str) -> None:
        async with self.session.client("s3", **self.client_options) as client:
            await client.delete_object(Bucket=self.bucket, Key=key)

    def url(self, key: str) -> str:
        return f"{self.base_url}/{key}"

    async def walk(self):
        async with self.session.client("s3", **self.client_options) as client:
            paginator = client.get_paginator("list_objects_v2")

            async for page in paginator.paginate(Bucket=self.bucket):
                for item in page.get("Contents", []):
                    yield item["Key"], item["LastModified"]


PROVIDERS: dict[StorageProvider, type[Storage]] = {StorageProvider.FILESYSTEM: FilesystemStorage, StorageProvider.S3: S3Storage}

storage: Storage = PROVIDERS[settings.storage.provider](settings.storage)
