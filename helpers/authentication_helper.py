"""Shared account and surface rules for optional sign-in methods."""

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from enums.authentication_surface import AuthenticationSurface
from enums.user import PANEL_ROLES
from enums.user_status import UserStatus
from helpers.authentication_error import AuthenticationError
from helpers.dates import now
from helpers.not_found_error import NotFoundError
from helpers.permission_error import PermissionError
from helpers.scope import belongs_to_tenant
from helpers.settings import settings
from models.user import User
from services.social_providers import PROVIDERS
from services.user_service import user_service


class AuthenticationHelper:
    @staticmethod
    def connections(surface: AuthenticationSurface, identities: list) -> list[dict]:
        connected = {identity.provider: identity for identity in identities}
        offered = []

        for provider, implementation in PROVIDERS.items():
            configuration = settings.authentication.social.get(provider)
            enabled = configuration is not None and AuthenticationHelper.available(configuration, surface)
            identity = connected.get(provider)

            if not enabled and identity is None:
                continue

            offered.append({"provider": provider, "label": implementation.label, "connected": identity is not None, "enabled": enabled, "created_at": identity.created_at if identity else None})

        return offered

    @staticmethod
    def methods(surface: AuthenticationSurface) -> dict:
        offered = []

        for provider, configuration in settings.authentication.social.items():
            if AuthenticationHelper.available(configuration, surface):
                offered.append({"provider": provider, "label": PROVIDERS[provider].label})

        return {"email_code": AuthenticationHelper.available(settings.authentication.email, surface), "social": offered}

    @staticmethod
    def available(configuration, surface: AuthenticationSurface) -> bool:
        offered = {AuthenticationSurface.SITE: configuration.site, AuthenticationSurface.ADMIN: configuration.admin}

        return configuration.enabled and offered[surface]

    @staticmethod
    def require_email(surface: AuthenticationSurface) -> None:
        if not AuthenticationHelper.available(settings.authentication.email, surface):
            raise NotFoundError("error.authentication-method-disabled")

    @staticmethod
    def require_social(provider, surface: AuthenticationSurface):
        configuration = settings.authentication.social.get(provider)

        if configuration is None or not AuthenticationHelper.available(configuration, surface):
            raise NotFoundError("error.authentication-method-disabled")

        return configuration

    @staticmethod
    def scope(tenant_id: int | None, surface: AuthenticationSurface):
        if surface == AuthenticationSurface.ADMIN:
            return or_(belongs_to_tenant(User.tenant_id, tenant_id), User.tenant_id.is_(None))

        return belongs_to_tenant(User.tenant_id, tenant_id)

    @staticmethod
    async def by_email(db: AsyncSession, tenant_id: int | None, email: str, surface: AuthenticationSurface) -> User | None:
        statement = select(User).where(User.email == email, AuthenticationHelper.scope(tenant_id, surface)).order_by(User.role.not_in(PANEL_ROLES), User.tenant_id.is_(None)).limit(1)

        return await db.scalar(statement)

    @staticmethod
    def ensure_access(user: User | None, surface: AuthenticationSurface) -> None:
        if user is None:
            raise AuthenticationError("error.invalid-credentials")

        if user.status != UserStatus.ACTIVE:
            raise AuthenticationError("error.account-blocked" if user.status == UserStatus.BLOCKED else "error.invalid-credentials")

        if surface == AuthenticationSurface.ADMIN and user.role not in PANEL_ROLES:
            raise AuthenticationError("error.panel-not-allowed")

    @staticmethod
    def ensure_scope(user: User, tenant_id: int | None, surface: AuthenticationSurface) -> None:
        if surface == AuthenticationSurface.ADMIN and user.tenant_id is None:
            return

        if user.tenant_id != tenant_id:
            raise PermissionError("error.account-of-another-brand")

    @staticmethod
    async def signed_in(db: AsyncSession, user: User | None, surface: AuthenticationSurface, tenant_id: int | None) -> User:
        AuthenticationHelper.ensure_access(user, surface)
        AuthenticationHelper.ensure_scope(user, tenant_id, surface)

        identifier = user.id
        epoch = user.session_epoch
        statement = update(User).where(User.id == identifier, User.status == UserStatus.ACTIVE, User.session_epoch == epoch, AuthenticationHelper.scope(tenant_id, surface)).values(last_login_at=now(), failed_sign_ins=0, sign_in_blocked_until=None)
        claimed = (await db.execute(statement)).rowcount == 1
        await db.commit()

        if not claimed:
            raise AuthenticationError("error.invalid-credentials")

        user = await user_service.get(db, identifier)
        AuthenticationHelper.ensure_access(user, surface)
        AuthenticationHelper.ensure_scope(user, tenant_id, surface)

        if user.session_epoch != epoch:
            raise AuthenticationError("error.invalid-credentials")

        return user
