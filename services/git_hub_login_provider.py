from authlib.integrations.httpx_client import AsyncOAuth2Client

from config.social_login_settings import SocialLoginSettings
from helpers.authentication_error import AuthenticationError
from helpers.o_auth_login_helper import OAuthLoginHelper
from models.social_login_attempt import SocialLoginAttempt
from services.social_login_provider import SocialLoginProvider
from services.social_profile import SocialProfile


class GitHubLoginProvider(SocialLoginProvider):
    label = "GitHub"
    authorization_url = "https://github.com/login/oauth/authorize"
    token_url = "https://github.com/login/oauth/access_token"
    scope = "user:email"
    pkce = True

    async def identify(self, client: AsyncOAuth2Client, configuration: SocialLoginSettings, attempt: SocialLoginAttempt, token: dict) -> SocialProfile:
        profile = await OAuthLoginHelper.read(client, "https://api.github.com/user")
        subject = OAuthLoginHelper.subject(profile, "id")
        response = await client.get("https://api.github.com/user/emails")
        response.raise_for_status()
        addresses = response.json()

        if not isinstance(addresses, list) or any(not isinstance(address, dict) for address in addresses):
            raise AuthenticationError("error.social-response-invalid")

        for address in addresses:
            if address.get("primary") is True and address.get("verified") is True:
                email = OAuthLoginHelper.verified_email({"email": address.get("email"), "email_verified": True})

                return SocialProfile(subject, email)

        return SocialProfile(subject)
