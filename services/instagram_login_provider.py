from authlib.integrations.httpx_client import AsyncOAuth2Client

from config.social_login_settings import SocialLoginSettings
from helpers.authentication_error import AuthenticationError
from helpers.o_auth_login_helper import OAuthLoginHelper
from models.social_login_attempt import SocialLoginAttempt
from services.social_login_provider import SocialLoginProvider
from services.social_profile import SocialProfile


class InstagramLoginProvider(SocialLoginProvider):
    label = "Instagram"
    authorization_url = "https://www.instagram.com/oauth/authorize"
    token_url = "https://api.instagram.com/oauth/access_token"
    scope = "instagram_business_basic"
    pkce = False

    def authorization_parameters(self, attempt: SocialLoginAttempt) -> dict:
        return {"enable_fb_login": "false", "force_reauth": "true"}

    async def exchange(self, client: AsyncOAuth2Client, configuration: SocialLoginSettings, attempt: SocialLoginAttempt, code: str) -> dict:
        response = await client.request("POST", self.token_url, data={"client_id": configuration.client_id, "client_secret": configuration.client_secret.get_secret_value(), "grant_type": "authorization_code", "redirect_uri": attempt.redirect_uri, "code": code}, withhold_token=True)
        response.raise_for_status()
        payload = response.json()

        entries = payload.get("data") if isinstance(payload, dict) else None

        if not isinstance(entries, list) or len(entries) != 1 or not isinstance(entries[0], dict):
            raise AuthenticationError("error.social-response-invalid")

        identity = entries[0]

        if not isinstance(identity.get("access_token"), str) or not identity["access_token"]:
            raise AuthenticationError("error.social-response-invalid")

        token = {"access_token": identity["access_token"], "token_type": "Bearer", "subject": OAuthLoginHelper.subject(identity, "user_id")}
        client.token = token

        return token

    async def identify(self, client: AsyncOAuth2Client, configuration: SocialLoginSettings, attempt: SocialLoginAttempt, token: dict) -> SocialProfile:
        profile = await OAuthLoginHelper.read(client, f"https://graph.instagram.com/{configuration.facebook_api_version}/me", params={"fields": "user_id,username"})
        subject = OAuthLoginHelper.subject(profile, "user_id")

        if subject != token["subject"]:
            raise AuthenticationError("error.social-response-invalid")

        return SocialProfile(subject)
