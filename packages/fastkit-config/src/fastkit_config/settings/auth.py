from pydantic import BaseModel, Field

from fastkit_config.settings.captcha import CaptchaSettings


class AuthSettings(BaseModel):
    login_identifier_types: list[str] = Field(
        default_factory=lambda: ["email", "username", "phone"]
    )
    session_cookie_name: str = "fastkit_session"
    password_min_length: int = 12
    password_max_length: int = 128
    jwt_algorithm: str = "HS256"
    access_token_ttl_seconds: int = 3600
    max_failed_logins: int = 5
    lockout_seconds: int = 900
    rate_limit_per_minute: int = 10
    captcha: CaptchaSettings = Field(default_factory=CaptchaSettings)
