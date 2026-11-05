from pydantic import BaseModel

from config.email_settings import EmailSettings


class TenantSettings(BaseModel):
    """What one tenant overrides, where a field left out keeps whatever the environment declares."""

    email: EmailSettings | None = None
