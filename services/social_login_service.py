import secrets
from datetime import timedelta

import httpx2
from authlib.integrations.base_client.errors import OAuthError
from joserfc.errors import JoseError
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from enums.authentication_surface import AuthenticationSurface
from enums.social_provider import SocialProvider
from enums.user import PANEL_ROLES
from enums.user_role import UserRole
from enums.user_status import UserStatus
from helpers.app_error import AppError
from helpers.authentication_error import AuthenticationError
from helpers.authentication_helper import AuthenticationHelper
from helpers.brand import Brand
from helpers.dates import now
from helpers.db import insert_or_read, refusing
from helpers.scope import belongs_to_tenant
from helpers.security import encrypt, generate_token
from helpers.settings import settings
from helpers.signing import digest
from helpers.validation_error import ValidationError
from models.social_identity import SocialIdentity
from models.social_login_attempt import SocialLoginAttempt
from models.user import User
from services.social_authorization import SocialAuthorization
from services.social_profile import SocialProfile
from services.social_providers import PROVIDERS
from services.user_service import user_service


class SocialLoginService:
    async def start(self, db: AsyncSession, brand: Brand, provider: SocialProvider, surface: AuthenticationSurface, next_path: str, user: User | None = None) -> SocialAuthorization:
        configuration = AuthenticationHelper.require_social(provider, surface)

        if user is not None:
            AuthenticationHelper.ensure_access(user, surface)
            AuthenticationHelper.ensure_scope(user, brand.id, surface)

        state = generate_token()
        browser = generate_token()
        attributes = {
            "tenant_id": brand.id,
            "user_id": user.id if user else None,
            "session_epoch": user.session_epoch if user else None,
            "surface": surface,
            "provider": provider,
            "state_digest": digest("social-state", state),
            "browser_digest": digest("login-browser", browser),
            "nonce": generate_token(),
            "verifier_encrypted": encrypt(generate_token()),
            "redirect_uri": brand.address(f"/account/social/{provider.value}/callback"),
            "next_path": next_path,
            "expires_at": now() + timedelta(seconds=settings.authentication.social_ttl),
        }
        attempt = SocialLoginAttempt(**attributes)
        address = await PROVIDERS[provider].authorization(configuration, attempt, state)
        db.add(attempt)
        await db.commit()

        return SocialAuthorization(attempt, address, state, browser)

    async def consume(self, db: AsyncSession, brand: Brand, provider: SocialProvider, state: str, browser: str) -> SocialLoginAttempt:
        attempt = await db.scalar(select(SocialLoginAttempt).where(SocialLoginAttempt.state_digest == digest("social-state", state)))

        if attempt is None:
            raise AuthenticationError("error.social-attempt-invalid")

        moment = now()
        scoped = SocialLoginAttempt.tenant_id.is_(None) if brand.id is None else SocialLoginAttempt.tenant_id == brand.id
        conditions = (scoped, SocialLoginAttempt.provider == provider, SocialLoginAttempt.state_digest == digest("social-state", state), SocialLoginAttempt.browser_digest == digest("login-browser", browser), SocialLoginAttempt.consumed_at.is_(None), SocialLoginAttempt.expires_at > moment)
        statement = update(SocialLoginAttempt).where(*conditions).values(consumed_at=moment)
        claimed = (await db.execute(statement)).rowcount == 1
        await db.commit()

        if not claimed:
            raise AuthenticationError("error.social-attempt-invalid")

        return attempt

    async def complete(self, db: AsyncSession, attempt: SocialLoginAttempt, code: str) -> User:
        configuration = AuthenticationHelper.require_social(attempt.provider, attempt.surface)
        provider = PROVIDERS[attempt.provider]

        try:
            async with provider.client(configuration, attempt) as client:
                token = await provider.exchange(client, configuration, attempt, code)
                profile = await provider.identify(client, configuration, attempt, token)
        except (httpx2.HTTPError, OAuthError) as error:
            raise AppError("error.social-unavailable", 503) from error
        except (JoseError, ValueError) as error:
            raise AuthenticationError("error.social-response-invalid") from error

        if attempt.user_id is not None:
            return await self.connect(db, attempt, profile)

        return await self.sign_in(db, attempt, profile)

    async def identity(self, db: AsyncSession, tenant_id: int | None, surface: AuthenticationSurface, provider: SocialProvider, subject: str) -> SocialIdentity | None:
        statement = select(SocialIdentity).join(User, User.id == SocialIdentity.user_id).where(SocialIdentity.provider == provider, SocialIdentity.subject == subject, AuthenticationHelper.scope(tenant_id, surface)).order_by(User.role.not_in(PANEL_ROLES), User.tenant_id.is_(None)).limit(1)

        return await db.scalar(statement)

    async def sign_in(self, db: AsyncSession, attempt: SocialLoginAttempt, profile: SocialProfile) -> User:
        surface = attempt.surface
        tenant_id = attempt.tenant_id
        linked = await self.identity(db, attempt.tenant_id, attempt.surface, attempt.provider, profile.subject)

        if linked is not None:
            user = await db.get(User, linked.user_id)

            return await AuthenticationHelper.signed_in(db, user, surface, tenant_id)

        if profile.email is not None and await AuthenticationHelper.by_email(db, attempt.tenant_id, profile.email, attempt.surface) is not None:
            raise ValidationError("error.social-link-required")

        if attempt.surface == AuthenticationSurface.ADMIN:
            raise AuthenticationError("error.panel-not-allowed")

        email = profile.email
        username = None if email else f"{attempt.provider.value}-{secrets.token_hex(12)}"

        if email is not None:
            await user_service.ensure_free(db, "email", email, attempt.tenant_id, None)

        user = User(tenant_id=attempt.tenant_id, email=email, username=username, password_hash="", role=UserRole.NORMAL, status=UserStatus.ACTIVE)

        async with refusing(db, "error.social-identity-in-use"):
            db.add(user)
            await db.flush()

            linked = SocialIdentity(tenant_id=user.tenant_id, user_id=user.id, provider=attempt.provider, subject=profile.subject)
            proposed = await insert_or_read(db, linked, select(SocialIdentity).where(belongs_to_tenant(SocialIdentity.tenant_id, attempt.tenant_id), SocialIdentity.provider == attempt.provider, SocialIdentity.subject == profile.subject))

            if proposed is not linked:
                user_id = proposed.user_id
                await db.rollback()
                user = await db.get(User, user_id)

                return await AuthenticationHelper.signed_in(db, user, surface, tenant_id)

            await db.commit()

        return await AuthenticationHelper.signed_in(db, user, surface, tenant_id)

    async def connect(self, db: AsyncSession, attempt: SocialLoginAttempt, profile: SocialProfile) -> User:
        user = await db.get(User, attempt.user_id)

        if user is None or user.session_epoch != attempt.session_epoch:
            raise AuthenticationError("error.social-attempt-invalid")

        AuthenticationHelper.ensure_access(user, attempt.surface)
        await user_service.hold(db, user.id)
        await db.refresh(user)
        AuthenticationHelper.ensure_access(user, attempt.surface)
        AuthenticationHelper.ensure_scope(user, attempt.tenant_id, attempt.surface)

        if user.session_epoch != attempt.session_epoch:
            raise AuthenticationError("error.social-attempt-invalid")

        async with refusing(db, "error.social-identity-in-use"):
            linked = await db.scalar(select(SocialIdentity).where(SocialIdentity.user_id == user.id, SocialIdentity.provider == attempt.provider))

            if linked is not None:
                if linked.subject != profile.subject:
                    raise ValidationError("error.social-provider-already-connected")

                await db.commit()

                return user

            db.add(SocialIdentity(tenant_id=user.tenant_id, user_id=user.id, provider=attempt.provider, subject=profile.subject))
            await db.commit()

        return user

    async def connections(self, db: AsyncSession, user: User) -> list[SocialIdentity]:
        return list((await db.scalars(select(SocialIdentity).where(SocialIdentity.user_id == user.id).order_by(SocialIdentity.provider.asc()))).all())

    async def disconnect(self, db: AsyncSession, user: User, provider: SocialProvider, surface: AuthenticationSurface) -> None:
        await user_service.hold(db, user.id)
        await db.refresh(user)
        AuthenticationHelper.ensure_access(user, surface)

        identities = await self.connections(db, user)
        enabled = {name for name, configuration in settings.authentication.social.items() if AuthenticationHelper.available(configuration, surface)}
        other_methods = any(identity.provider != provider and identity.provider in enabled for identity in identities)
        email_available = bool(user.email) and AuthenticationHelper.available(settings.authentication.email, surface)

        if not user.has_password and not email_available and not other_methods:
            raise ValidationError("error.last-sign-in-method")

        await db.execute(delete(SocialIdentity).where(SocialIdentity.user_id == user.id, SocialIdentity.provider == provider))
        await db.commit()


social_login_service = SocialLoginService()
