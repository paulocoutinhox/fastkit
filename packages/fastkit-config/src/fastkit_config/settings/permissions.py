from pydantic import BaseModel


class PermissionsSettings(BaseModel):
    store: str = "memory"
