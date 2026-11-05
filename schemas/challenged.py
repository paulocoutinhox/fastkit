from schemas.base_schema import BaseSchema
from schemas.common import CaptchaAnswer, CaptchaToken


class Challenged(BaseSchema):
    """A form anybody may send carries the challenge the environment declared, the same wherever it is drawn."""

    captcha_answer: CaptchaAnswer = None
    captcha_token: CaptchaToken = None
