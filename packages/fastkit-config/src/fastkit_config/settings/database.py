from pydantic import BaseModel


class DatabaseSettings(BaseModel):
    url: str = "sqlite+aiosqlite:///./data/app.db"
    pool_pre_ping: bool = True
    pool_recycle: int = 1800
    echo: bool = False
