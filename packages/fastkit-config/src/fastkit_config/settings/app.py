from pydantic import BaseModel


class AppSettings(BaseModel):
    name: str = "FastKit App"
    environment: str = "dev"
    debug: bool = False
    timezone: str = "UTC"
    secret_key: str = "change-me"
