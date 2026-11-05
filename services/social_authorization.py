from dataclasses import dataclass

from models.social_login_attempt import SocialLoginAttempt


@dataclass(frozen=True)
class SocialAuthorization:
    attempt: SocialLoginAttempt
    url: str
    state: str
    browser: str
