from pydantic import BaseModel, Field


class EmailLoginSettings(BaseModel):
    enabled: bool = False
    site: bool = True
    admin: bool = True
    code_ttl: int = Field(default=600, ge=60, le=1800)
    resend_interval: int = Field(default=60, ge=30, le=600)
    max_attempts: int = Field(default=5, ge=1, le=10)
