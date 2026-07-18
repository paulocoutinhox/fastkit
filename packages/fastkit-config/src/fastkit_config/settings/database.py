from pydantic import BaseModel


class DatabaseSettings(BaseModel):
    url: str = "sqlite+aiosqlite:///./data/app.db"
    pool_pre_ping: bool = True
    echo: bool = False
