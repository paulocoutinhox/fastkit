from pydantic import BaseModel


class StorageSettings(BaseModel):
    provider: str = "local"
    root: str = "./data/media"
    base_url: str = "/media"
