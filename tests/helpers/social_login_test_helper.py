import httpx2
import jwt
from authlib.integrations.httpx_client import AsyncOAuth2Client

from enums.social_provider import SocialProvider
from helpers.dates import now
from services.oidc_login_provider import OidcLoginProvider
from services.social_providers import PROVIDERS


class SocialLoginTestHelper:
    @staticmethod
    def answer_provider(monkeypatch, provider_name, configuration, attempt, keys, claims=None, userinfo=None, token_changes=None, responses=None):
        provider = PROVIDERS[provider_name]
        seen = []
        identity = {"sub": "provider-account", "email": "social@example.com", "email_verified": True}
        moment = int(now().timestamp())
        issuer = provider.issuer(configuration) if isinstance(provider, OidcLoginProvider) else "unused"
        payload = {**identity, "iss": issuer, "aud": configuration.client_id, "iat": moment, "exp": moment + 300, "nonce": attempt.nonce, **(claims or {})}
        encoded = jwt.encode(payload, keys["private"], algorithm="RS256", headers={"kid": "test-key"})
        profile = {**identity, **(userinfo or {})}

        def answer(request):
            seen.append(request)
            address = str(request.url).split("?")[0]
            endpoint = provider.token_url.format(tenant=configuration.microsoft_tenant, version=configuration.facebook_api_version)

            if responses is not None and address in responses:
                response = responses[address]

                if isinstance(response, Exception):
                    raise response

                return response

            if address == endpoint:
                if provider_name == SocialProvider.INSTAGRAM:
                    return httpx2.Response(200, json={"data": [{"access_token": "provider-token", "user_id": "provider-account", **(token_changes or {})}]})

                return httpx2.Response(200, json={"access_token": "provider-token", "token_type": "Bearer", "expires_in": 3600, "id_token": encoded, **(token_changes or {})})

            if isinstance(provider, OidcLoginProvider) and address == provider.jwks_url:
                return httpx2.Response(200, json=keys["jwks"])

            if isinstance(provider, OidcLoginProvider) and address == provider.userinfo_url:
                return httpx2.Response(200, json=profile)

            if address == "https://api.github.com/user":
                return httpx2.Response(200, json={"id": "provider-account"})

            if address == "https://api.github.com/user/emails":
                return httpx2.Response(200, json=[{"email": "social@example.com", "primary": True, "verified": True}])

            if address == f"https://graph.facebook.com/{configuration.facebook_api_version}/me":
                return httpx2.Response(200, json={"id": "provider-account"})

            if address == f"https://graph.instagram.com/{configuration.facebook_api_version}/me":
                return httpx2.Response(200, json={"user_id": "provider-account", "username": "someone"})

            raise AssertionError(f"unexpected provider request: {request.url}")

        def client(*args, **kwargs):
            return AsyncOAuth2Client(*args, transport=httpx2.MockTransport(answer), **kwargs)

        monkeypatch.setattr("services.social_login_provider.AsyncOAuth2Client", client)

        return seen
