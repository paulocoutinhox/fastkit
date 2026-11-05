import hashlib
import hmac

from authlib.integrations.httpx_client import AsyncOAuth2Client

from config.social_login_settings import SocialLoginSettings
from helpers.o_auth_login_helper import OAuthLoginHelper
from models.social_login_attempt import SocialLoginAttempt
from services.social_login_provider import SocialLoginProvider
from services.social_profile import SocialProfile


class FacebookLoginProvider(SocialLoginProvider):
    label = "Facebook"
    authorization_url = "https://www.facebook.com/{version}/dialog/oauth"
    token_url = "https://graph.facebook.com/{version}/oauth/access_token"
    scope = "public_profile"
    pkce = False

    async def identify(self, client: AsyncOAuth2Client, configuration: SocialLoginSettings, attempt: SocialLoginAttempt, token: dict) -> SocialProfile:
        proof = hmac.new(configuration.client_secret.get_secret_value().encode(), token["access_token"].encode(), hashlib.sha256).hexdigest()
        profile = await OAuthLoginHelper.read(client, f"https://graph.facebook.com/{configuration.facebook_api_version}/me", params={"fields": "id", "appsecret_proof": proof})

        return SocialProfile(OAuthLoginHelper.subject(profile, "id"))
