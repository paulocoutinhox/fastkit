from config.social_login_settings import SocialLoginSettings
from services.oidc_login_provider import OidcLoginProvider


class LinkedInLoginProvider(OidcLoginProvider):
    label = "LinkedIn"
    authorization_url = "https://www.linkedin.com/oauth/v2/authorization"
    token_url = "https://www.linkedin.com/oauth/v2/accessToken"
    jwks_url = "https://www.linkedin.com/oauth/openid/jwks"
    userinfo_url = "https://api.linkedin.com/v2/userinfo"
    scope = "openid profile email"
    pkce = False

    def issuer(self, configuration: SocialLoginSettings) -> str:
        return "https://www.linkedin.com/oauth"
