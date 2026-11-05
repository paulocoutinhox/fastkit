from pydantic import BaseModel, Field, SecretStr


class SocialLoginSettings(BaseModel):
    enabled: bool = False
    site: bool = True
    admin: bool = True
    client_id: str = ""
    client_secret: SecretStr = SecretStr("")
    team_id: str = ""
    key_id: str = ""
    private_key: SecretStr = SecretStr("")
    microsoft_tenant: str = Field(default="consumers", pattern=r"^(consumers|[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})$")
    facebook_api_version: str = Field(default="v26.0", pattern=r"^v[0-9]{2}\.0$")
