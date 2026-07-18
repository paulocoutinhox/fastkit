from pydantic import BaseModel


class CacheSettings(BaseModel):
    provider: str = "file"
    default_ttl_seconds: int = 300
    directory: str = "./data/cache"
