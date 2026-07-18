from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import update

from fastkit_core.errors.exceptions import AuthenticationError
from fastkit_accounts.models import User
from fastkit_auth.errors import ACCOUNT_INACTIVE, ACCOUNT_LOCKED, AMBIGUOUS_IDENTITY, INVALID_CREDENTIALS
from fastkit_auth.models import Session
from fastkit_auth.helpers import ensure_aware
from fastkit_tenancy.constants import to_api
from fastkit_tenancy.service import resolve_effective_tenant


@dataclass(frozen=True)
class LoginResult:
    user: User
    session: Session
    token: str
    session_token: str
    effective_tenant_id: int


class AuthService:
    """Coordinates the full password login flow with brute-force and captcha policy."""

    def __init__(self, database, account_service, password_service, session_service, token_service, rate_limiter, captcha, max_failed: int = 5, lockout_seconds: int = 900, clock=None):
        self._database = database
        self._accounts = account_service
        self._passwords = password_service
        self._sessions = session_service
        self._tokens = token_service
        self._rate_limiter = rate_limiter
        self._captcha = captcha
        self._max_failed = max_failed
        self._lockout_seconds = lockout_seconds
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    async def login(self, identifier_type: str, identifier_value: str, password: str, requested_tenant_id: int | None = 0, captcha: dict | None = None, ip_address: str | None = None, user_agent: str | None = None) -> LoginResult:
        if identifier_type not in self._accounts.identifier_types():
            raise AuthenticationError(INVALID_CREDENTIALS, message="invalid credentials")

        normalized_identifier = self._accounts.normalize_identifier(identifier_type, identifier_value)
        self._rate_limiter.hit(ip_address, requested_tenant_id, f"{identifier_type}:{normalized_identifier}")

        await self._captcha.verify(captcha)

        candidates = await self._accounts.find_candidates(requested_tenant_id, identifier_type, identifier_value)
        verifiable = any(candidate.password_hash for candidate in candidates)
        matches = [candidate for candidate in candidates if candidate.password_hash and self._passwords.verify(candidate.password_hash, password)]

        if not matches:
            # keep the cost constant when no real argon2 verify ran, so passwordless accounts are not an enumeration oracle
            if not verifiable:
                self._passwords.dummy_verify(password)

            await self._register_failures(candidates)
            raise AuthenticationError(INVALID_CREDENTIALS, message="invalid credentials")

        if len(matches) > 1:
            raise AuthenticationError(AMBIGUOUS_IDENTITY, message="identifier matches more than one account")

        user = matches[0]
        self._assert_can_authenticate(user)

        effective_tenant_id = resolve_effective_tenant(to_api(user.tenant_id), requested_tenant_id)
        record, raw_token = await self._sessions.create(user.id, to_api(user.tenant_id), effective_tenant_id, ip_address, user_agent)

        await self._on_success(user, password)
        token = self._tokens.issue(str(user.id), to_api(user.tenant_id), effective_tenant_id, str(record.id))

        self._rate_limiter.reset(ip_address, requested_tenant_id, f"{identifier_type}:{normalized_identifier}")

        return LoginResult(user=user, session=record, token=token, session_token=raw_token, effective_tenant_id=effective_tenant_id)

    async def logout(self, raw_token: str) -> bool:
        return await self._sessions.revoke(raw_token)

    def _assert_can_authenticate(self, user: User) -> None:
        if not user.is_active:
            raise AuthenticationError(ACCOUNT_INACTIVE, message="account is inactive")

        if user.locked_until is not None and ensure_aware(user.locked_until) > self._clock():
            raise AuthenticationError(ACCOUNT_LOCKED, message="account is temporarily locked")

    async def _register_failures(self, candidates: list[User]) -> None:
        if not candidates:
            return

        now = self._clock()

        locked_until = now + timedelta(seconds=self._lockout_seconds)

        async with self._database.session_factory() as session:
            for candidate in candidates:
                await session.execute(update(User).where(User.id == candidate.id).values(failed_login_count=User.failed_login_count + 1))
                await session.execute(update(User).where(User.id == candidate.id, User.failed_login_count >= self._max_failed).values(locked_until=locked_until))

            await session.commit()

    async def _on_success(self, user: User, password: str) -> None:
        now = self._clock()

        # upgrade the stored hash in place when the argon2 parameters changed since it was written
        rehashed = self._passwords.rehash(password) if self._passwords.needs_rehash(user.password_hash) else None

        async with self._database.session_factory() as session:
            stored = await session.get(User, user.id)

            if stored is None:
                return

            stored.failed_login_count = 0
            stored.locked_until = None
            stored.last_login_at = now

            if rehashed is not None:
                stored.password_hash = rehashed

            await session.commit()

        user.failed_login_count = 0
        user.locked_until = None
        user.last_login_at = now

        if rehashed is not None:
            user.password_hash = rehashed
