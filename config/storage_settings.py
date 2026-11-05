from pathlib import Path

from pydantic import BaseModel

from config.base import DATA_DIR
from enums.storage_provider import StorageProvider


class StorageSettings(BaseModel):
    provider: StorageProvider
    base_url: str
    root: Path = DATA_DIR / "media"
    bucket: str = ""
    region: str = ""
    endpoint_url: str = ""
    access_key: str = ""
    secret_key: str = ""
    sweep_orphans: bool = True
    orphan_grace_hours: int = 24
