from pydantic import BaseModel, Field


class CaptchaSettings(BaseModel):
    provider: str = "disabled"
    site_key: str = ""
    secret_key: str = ""
    action: str = "admin_login"
    minimum_score: float = 0.5
    allowed_hostnames: list[str] = Field(default_factory=list)
    timeout_seconds: int = 5
    image_length: int = 5
    challenge_ttl_seconds: int = 300
