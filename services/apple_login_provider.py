from datetime import timedelta

import jwt

from config.social_login_settings import SocialLoginSettings
from helpers.dates import now
from helpers.o_auth_login_helper import OAuthLoginHelper
from models.social_login_attempt import SocialLoginAttempt
from services.oidc_login_provider import OidcLoginProvider


class AppleLoginProvider(OidcLoginProvider):
    label = "Apple"
    authorization_url = "https://appleid.apple.com/auth/authorize"
    token_url = "https://appleid.apple.com/auth/token"
    jwks_url = "https://appleid.apple.com/auth/keys"
    userinfo_url = None
    scope = "openid email"
    pkce = False

    def issuer(self, configuration: SocialLoginSettings) -> str:
        return "https://appleid.apple.com"

    def authorization_parameters(self, attempt: SocialLoginAttempt) -> dict:
        return {**super().authorization_parameters(attempt), "response_mode": "form_post"}

    def client_secret(self, configuration: SocialLoginSettings) -> str:
        moment = now()
        claims = {"iss": configuration.team_id, "sub": configuration.client_id, "aud": "https://appleid.apple.com", "iat": int(moment.timestamp()), "exp": int((moment + timedelta(minutes=5)).timestamp())}

        return jwt.encode(claims, configuration.private_key.get_secret_value(), algorithm="ES256", headers={"kid": configuration.key_id})

    def verified_email(self, claims: dict) -> str | None:
        verified = claims.get("email_verified")

        return OAuthLoginHelper.verified_email({**claims, "email_verified": verified is True or verified == "true"})
