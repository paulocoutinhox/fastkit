from pydantic import BaseModel, Field


class I18nSettings(BaseModel):
    default_locale: str = "en"
    supported_locales: list[str] = Field(default_factory=lambda: ["en", "pt"])
