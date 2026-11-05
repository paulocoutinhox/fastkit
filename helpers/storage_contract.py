"""The storage contract used by the application."""

from abc import ABC, abstractmethod
from typing import AsyncIterator, BinaryIO


class Storage(ABC):
    """Where a stored file lives, which is a directory of this machine or a bucket every copy of the process reaches."""

    @abstractmethod
    async def save(self, key: str, data: bytes | BinaryIO, content_type: str) -> str: ...

    @abstractmethod
    async def delete(self, key: str) -> None: ...

    # Every provider serves a file from the address it was configured with, and one written twice is the one that drifts.
    def url(self, key: str) -> str:
        return f"{self.base_url}/{key}"

    @abstractmethod
    # The only one that answers a stream instead of a value, so the contract says so: a provider that writes it as a plain method is read with `async for` and fails there.
    def walk(self) -> AsyncIterator[str]: ...
