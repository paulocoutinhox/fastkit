from enums.captcha import CaptchaProvider
from schemas.common import BaseSchema


class CredentialSchema(BaseSchema):
    field: str
    label: str
    hint: str


class ChallengeSchema(BaseSchema):
    """One challenge, minted for the form about to be sent, where the half that proves the answer stays signed inside the token."""

    provider: CaptchaProvider
    token: str
    image: str
    site_key: str


class VisitorSchema(BaseSchema):
    """A name signed by this side, which an application keeps and sends back when it counts a banner."""

    visitor: str


class PermissionsResponse(BaseSchema):
    """The resources this account reaches, which is what the panel draws a menu out of."""

    resources: list[str]

    # An account that belongs to a brand writes into that brand and no other, so the panel stops drawing a field with one option.
    confined: bool


class MetaResponse(BaseSchema):
    name: str
    environment: str
    version: str
    storage_base_url: str
    enums: dict[str, list[str]]
    provider_credentials: dict[str, list[CredentialSchema]]
    timezones: list[str]


class HealthResponse(BaseSchema):
    status: str
