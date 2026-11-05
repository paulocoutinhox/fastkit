from pydantic import BaseModel


class DatabaseSettings(BaseModel):
    url: str
    echo: bool = False
    pool_size: int = 10
    max_overflow: int = 20
    pool_recycle: int = 3600
