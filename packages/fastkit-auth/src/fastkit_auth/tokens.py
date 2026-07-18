from datetime import datetime, timedelta, timezone

import jwt

from fastkit_core.errors.codes import AUTHENTICATION_FAILED
from fastkit_core.errors.exceptions import AuthenticationError


class TokenService:
    """Issues and verifies signed JWT access tokens for authenticated sessions."""

    def __init__(
        self, secret_key: str, algorithm: str = "HS256", ttl_seconds: int = 3600
    ):
        self._secret_key = secret_key
        self._algorithm = algorithm
        self._ttl_seconds = ttl_seconds

    def issue(
        self,
        subject: str,
        identity_tenant_id: int | None,
        effective_tenant_id: int | None,
        session_id: str,
        issued_at: datetime | None = None,
    ) -> str:
        now = issued_at or datetime.now(timezone.utc)

        payload = {
            "sub": subject,
            "sid": session_id,
            "itid": identity_tenant_id,
            "etid": effective_tenant_id,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(seconds=self._ttl_seconds)).timestamp()),
        }

        return jwt.encode(payload, self._secret_key, algorithm=self._algorithm)

    def verify(self, token: str) -> dict:
        try:
            return jwt.decode(token, self._secret_key, algorithms=[self._algorithm])
        except jwt.ExpiredSignatureError as error:
            raise AuthenticationError(
                AUTHENTICATION_FAILED, message="session token expired"
            ) from error
        except jwt.InvalidTokenError as error:
            raise AuthenticationError(
                AUTHENTICATION_FAILED, message="invalid session token"
            ) from error
