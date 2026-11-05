from config.social_login_settings import SocialLoginSettings
from services.oidc_login_provider import OidcLoginProvider


class MicrosoftLoginProvider(OidcLoginProvider):
    label = "Microsoft"
    authorization_url = "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/authorize"
    token_url = "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"
    jwks_url = "https://login.microsoftonline.com/common/discovery/v2.0/keys"
    userinfo_url = "https://graph.microsoft.com/oidc/userinfo"
    scope = "openid email profile"
    pkce = True

    def issuer(self, configuration: SocialLoginSettings) -> str:
        tenant = configuration.microsoft_tenant

        if tenant == "consumers":
            tenant = "9188040d-6c67-4c5b-b112-36a304b66dad"

        return f"https://login.microsoftonline.com/{tenant.lower()}/v2.0"

    def verified_email(self, claims: dict) -> str | None:
        return None
