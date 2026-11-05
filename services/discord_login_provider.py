from config.social_login_settings import SocialLoginSettings
from services.oidc_login_provider import OidcLoginProvider


class DiscordLoginProvider(OidcLoginProvider):
    label = "Discord"
    authorization_url = "https://discord.com/api/oauth2/authorize"
    token_url = "https://discord.com/api/oauth2/token"
    jwks_url = "https://discord.com/api/oauth2/keys"
    userinfo_url = "https://discord.com/api/oauth2/userinfo"
    scope = "openid identify email"
    pkce = True

    def issuer(self, configuration: SocialLoginSettings) -> str:
        return "https://discord.com"
