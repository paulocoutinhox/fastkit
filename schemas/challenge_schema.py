from enums.captcha_provider import CaptchaProvider
from schemas.base_schema import BaseSchema


class ChallengeSchema(BaseSchema):
    """One challenge, minted for the form about to be sent, where the half that proves the answer stays signed inside the token."""

    provider: CaptchaProvider
    token: str
    image: str
    site_key: str
