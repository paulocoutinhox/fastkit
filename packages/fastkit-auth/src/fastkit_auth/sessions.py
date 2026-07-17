import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from fastkit_auth.models import Session, SessionStatus
from fastkit_auth.helpers import ensure_aware


def hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


class SessionService:
    """Creates, validates and revokes opaque server-side sessions."""

    def __init__(self, session_factory, ttl_seconds: int = 3600, clock=None):
        self._session_factory = session_factory
        self._ttl_seconds = ttl_seconds
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    async def create(self, user_id, identity_tenant_id: int | None, effective_tenant_id: int | None, ip_address: str | None = None, user_agent: str | None = None) -> tuple[Session, str]:
        raw_token = secrets.token_urlsafe(32)
        now = self._clock()

        record = Session(
            user_id=user_id,
            identity_tenant_id=identity_tenant_id,
            effective_tenant_id=effective_tenant_id,
            token_hash=hash_token(raw_token),
            ip_address=ip_address,
            user_agent=user_agent,
            last_seen_at=now,
            expires_at=now + timedelta(seconds=self._ttl_seconds),
        )

        async with self._session_factory() as session:
            session.add(record)
            await session.commit()
            await session.refresh(record)

        return record, raw_token

    async def validate(self, raw_token: str) -> Session | None:
        token_hash = hash_token(raw_token)
        now = self._clock()

        async with self._session_factory() as session:
            record = (await session.execute(select(Session).where(Session.token_hash == token_hash))).scalar_one_or_none()

            if record is None or record.status != SessionStatus.active.value:
                return None

            if ensure_aware(record.expires_at) <= now:
                record.status = SessionStatus.expired.value
                await session.commit()

                return None

            record.last_seen_at = now
            await session.commit()
            await session.refresh(record)

            return record

    async def revoke(self, raw_token: str) -> bool:
        token_hash = hash_token(raw_token)
        now = self._clock()

        async with self._session_factory() as session:
            record = (await session.execute(select(Session).where(Session.token_hash == token_hash))).scalar_one_or_none()

            if record is None:
                return False

            record.status = SessionStatus.revoked.value
            record.revoked_at = now
            await session.commit()

            return True
