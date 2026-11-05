from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from pydantic import BaseModel, Field, model_validator

from config.email_login_settings import EmailLoginSettings
from config.social_login_settings import SocialLoginSettings
from enums.social_provider import SocialProvider


class AuthenticationSettings(BaseModel):
    email: EmailLoginSettings = Field(default_factory=EmailLoginSettings)
    social: dict[SocialProvider, SocialLoginSettings] = Field(default_factory=dict)
    social_ttl: int = Field(default=600, ge=60, le=1800)
    ticket_ttl: int = Field(default=60, ge=30, le=120)

    @model_validator(mode="after")
    def enabled_providers_have_credentials(self):
        for provider, configuration in self.social.items():
            if not configuration.enabled:
                continue

            if not configuration.client_id.strip():
                raise ValueError(f"{provider.value} requires a client_id")

            if provider == SocialProvider.APPLE:
                if not configuration.team_id or not configuration.key_id or not configuration.private_key.get_secret_value():
                    raise ValueError("apple requires team_id, key_id and private_key")

                key = serialization.load_pem_private_key(configuration.private_key.get_secret_value().encode(), password=None)

                if not isinstance(key, ec.EllipticCurvePrivateKey) or not isinstance(key.curve, ec.SECP256R1):
                    raise ValueError("apple requires an ES256 private key")

                continue

            if not configuration.client_secret.get_secret_value():
                raise ValueError(f"{provider.value} requires a client_secret")

        return self
