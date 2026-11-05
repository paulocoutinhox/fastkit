from abc import ABC, abstractmethod

from authlib.integrations.httpx_client import AsyncOAuth2Client

from config.social_login_settings import SocialLoginSettings
from helpers.o_auth_login_helper import OAuthLoginHelper
from models.social_login_attempt import SocialLoginAttempt
from services.social_profile import SocialProfile

TIMEOUT = 10.0


class SocialLoginProvider(ABC):
    label: str
    authorization_url: str
    token_url: str
    scope: str
    pkce: bool

    def client(self, configuration: SocialLoginSettings, attempt: SocialLoginAttempt) -> AsyncOAuth2Client:
        options = {"scope": self.scope, "redirect_uri": attempt.redirect_uri, "code_challenge_method": "S256" if self.pkce else None, "token_endpoint_auth_method": "client_secret_post"}

        client = AsyncOAuth2Client(configuration.client_id, self.client_secret(configuration), **options, timeout=TIMEOUT, follow_redirects=False, trust_env=False, headers={"Accept": "application/json"})
        client.register_compliance_hook("access_token_response", OAuthLoginHelper.token_response)

        return client

    def client_secret(self, configuration: SocialLoginSettings) -> str:
        return configuration.client_secret.get_secret_value()

    async def authorization(self, configuration: SocialLoginSettings, attempt: SocialLoginAttempt, state: str) -> str:
        async with self.client(configuration, attempt) as client:
            endpoint = self.authorization_url.format(tenant=configuration.microsoft_tenant, version=configuration.facebook_api_version)
            address, _ = client.create_authorization_url(endpoint, state=state, code_verifier=OAuthLoginHelper.code_verifier(attempt.verifier_encrypted) if self.pkce else None, **self.authorization_parameters(attempt))

        return address

    def authorization_parameters(self, attempt: SocialLoginAttempt) -> dict:
        return {}

    async def exchange(self, client: AsyncOAuth2Client, configuration: SocialLoginSettings, attempt: SocialLoginAttempt, code: str) -> dict:
        endpoint = self.token_url.format(tenant=configuration.microsoft_tenant, version=configuration.facebook_api_version)

        return await client.fetch_token(endpoint, code=code, code_verifier=OAuthLoginHelper.code_verifier(attempt.verifier_encrypted) if self.pkce else None)

    @abstractmethod
    async def identify(self, client: AsyncOAuth2Client, configuration: SocialLoginSettings, attempt: SocialLoginAttempt, token: dict) -> SocialProfile:
        """Read the immutable identity proved by the provider token."""
