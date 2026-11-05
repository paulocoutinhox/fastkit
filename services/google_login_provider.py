from config.social_login_settings import SocialLoginSettings
from services.oidc_login_provider import OidcLoginProvider


class GoogleLoginProvider(OidcLoginProvider):
    label = "Google"
    authorization_url = "https://accounts.google.com/o/oauth2/v2/auth"
    token_url = "https://oauth2.googleapis.com/token"
    jwks_url = "https://www.googleapis.com/oauth2/v3/certs"
    userinfo_url = "https://openidconnect.googleapis.com/v1/userinfo"
    scope = "openid email"
    pkce = True
    alternate_issuers = ("accounts.google.com",)

    def issuer(self, configuration: SocialLoginSettings) -> str:
        return "https://accounts.google.com"
