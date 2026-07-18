from pydantic import BaseModel


class ProfileUpdate(BaseModel):
    display_name: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    preferred_locale: str | None = None
    timezone: str | None = None
