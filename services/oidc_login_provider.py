from abc import abstractmethod

from authlib.integrations.httpx_client import AsyncOAuth2Client

from config.social_login_settings import SocialLoginSettings
from helpers.authentication_error import AuthenticationError
from helpers.o_auth_login_helper import OAuthLoginHelper
from models.social_login_attempt import SocialLoginAttempt
from services.social_login_provider import SocialLoginProvider
from services.social_profile import SocialProfile


class OidcLoginProvider(SocialLoginProvider):
    jwks_url: str
    userinfo_url: str | None
    alternate_issuers: tuple[str, ...] = ()

    def authorization_parameters(self, attempt: SocialLoginAttempt) -> dict:
        return {"nonce": attempt.nonce}

    @abstractmethod
    def issuer(self, configuration: SocialLoginSettings) -> str:
        """Name the trusted issuer for this configured provider application."""

    def verified_email(self, claims: dict) -> str | None:
        return OAuthLoginHelper.verified_email(claims)

    async def identify(self, client: AsyncOAuth2Client, configuration: SocialLoginSettings, attempt: SocialLoginAttempt, token: dict) -> SocialProfile:
        encoded = token.get("id_token")

        if not isinstance(encoded, str):
            raise AuthenticationError("error.social-response-invalid")

        keys = await OAuthLoginHelper.read(client, self.jwks_url, withhold_token=True)
        issuers = (self.issuer(configuration), *self.alternate_issuers)
        claims = await OAuthLoginHelper.claims(encoded, keys, issuers, configuration.client_id, attempt.nonce, token["access_token"])
        subject = OAuthLoginHelper.subject(claims, "sub")

        if self.userinfo_url is not None:
            information = await OAuthLoginHelper.read(client, self.userinfo_url)

            if OAuthLoginHelper.subject(information, "sub") != subject:
                raise AuthenticationError("error.social-response-invalid")

            return SocialProfile(subject, self.verified_email(information))

        return SocialProfile(subject, self.verified_email(claims))
