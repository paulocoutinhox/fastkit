from dataclasses import dataclass

from fastkit_storage.provider.status import StorageStatus


@dataclass(frozen=True)
class StorageHealth:
    status: StorageStatus
    detail: str | None = None
