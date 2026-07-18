from pydantic import BaseModel, Field


class AdminSettings(BaseModel):
    enabled: bool = True
    path: str = "/admin"
    api_path: str = "/api"
    theme: str = "tabler"
    page_size: int = 25
    page_size_options: list[int] = Field(default_factory=lambda: [10, 25, 50, 100])
