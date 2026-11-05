"""Strict provider response parsing and OpenID Connect identity validation."""

import asyncio

from authlib.oidc.core import CodeIDToken
from joserfc import jwt
from joserfc.errors import JoseError
from joserfc.jwk import KeySet
from pydantic import TypeAdapter, ValidationError

from helpers.authentication_error import AuthenticationError
from helpers.security import decrypt
from schemas.common import EmailAddress


class OAuthLoginHelper:
    email_type = TypeAdapter(EmailAddress)

    @staticmethod
    def code_verifier(encrypted: str) -> str:
        value = decrypt(encrypted)

        if value is None:
            raise AuthenticationError("error.social-attempt-invalid")

        return value

    @staticmethod
    def token_response(response):
        response.raise_for_status()
        payload = response.json()

        if not isinstance(payload, dict):
            raise AuthenticationError("error.social-response-invalid")

        if "error" in payload:
            if not isinstance(payload["error"], str) or not payload["error"]:
                raise AuthenticationError("error.social-response-invalid")

            return response

        if not isinstance(payload.get("access_token"), str) or not payload["access_token"] or not isinstance(payload.get("token_type"), str) or payload["token_type"].lower() != "bearer":
            raise AuthenticationError("error.social-response-invalid")

        return response

    @staticmethod
    async def read(client, url: str, **options) -> dict:
        response = await client.request("GET", url, **options)
        response.raise_for_status()
        payload = response.json()

        if not isinstance(payload, dict):
            raise AuthenticationError("error.social-response-invalid")

        return payload

    @staticmethod
    def subject(payload: dict, field: str) -> str:
        value = payload.get(field)

        if isinstance(value, bool) or not isinstance(value, (str, int)) or not str(value).strip() or len(str(value)) > 255:
            raise AuthenticationError("error.social-response-invalid")

        return str(value)

    @staticmethod
    def verified_email(payload: dict) -> str | None:
        if payload.get("email_verified") is not True or not payload.get("email"):
            return None

        try:
            return str(OAuthLoginHelper.email_type.validate_python(payload["email"])).lower()
        except ValidationError as error:
            raise AuthenticationError("error.social-response-invalid") from error

    @staticmethod
    async def claims(encoded: str, keys: dict, issuers: tuple[str, ...], client_id: str, nonce: str, access_token: str) -> dict:
        return await asyncio.to_thread(OAuthLoginHelper.validate_claims, encoded, keys, issuers, client_id, nonce, access_token)

    @staticmethod
    def validate_claims(encoded: str, keys: dict, issuers: tuple[str, ...], client_id: str, nonce: str, access_token: str) -> dict:
        try:
            trusted = KeySet.import_key_set(keys)
            decoded = jwt.decode(encoded, trusted, algorithms=["RS256"])
        except (JoseError, ValueError, KeyError, TypeError) as error:
            raise AuthenticationError("error.social-response-invalid") from error
        options = {"iss": {"essential": True, "values": list(issuers)}, "aud": {"essential": True, "value": client_id}, "sub": {"essential": True}, "exp": {"essential": True}, "iat": {"essential": True}}
        claims = CodeIDToken(decoded.claims, decoded.header, options=options, params={"client_id": client_id, "nonce": nonce, "access_token": access_token})
        claims.validate(leeway=30)

        return dict(claims)
