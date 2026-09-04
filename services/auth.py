from datetime import timedelta

from sqlalchemy import or_, update
from sqlalchemy.ext.asyncio import AsyncSession

from enums.user import PANEL_ROLES, UserRole, UserStatus
from helpers.brand import Brand
from helpers.dates import now
from helpers.errors import AuthenticationError, ValidationError
from helpers.i18n import current_locale
from helpers.security import generate_token, hash_password, no_such_account, verify_password
from helpers.settings import settings
from models.user import User
from services.email import email_service
from services.language import language_service
from services.user import user_service


class AuthService:
    """Everything that turns a person into a session, where the token never expires so what gates access is the account status."""

    async def authenticate(self, db: AsyncSession, tenant_id: int | None, login: str, password: str) -> User:
        user = await user_service.find_by_login(db, login, tenant_id)
        settled = await verify_password(password, user.password_hash if user is not None else no_such_account) and user is not None

        if user is not None and not settled:
            await self.count_failure(db, user)

        if not settled:
            raise AuthenticationError("error.invalid-credentials")

        # Only somebody who already knows the password is told to wait, so a wrong one never says whether the account is there.
        if self.blocked(user):
            raise AuthenticationError("error.too-many-attempts")

        self.ensure_usable(user)

        user.failed_sign_ins = 0
        user.sign_in_blocked_until = None
        user.last_login_at = now()
        await db.commit()

        return await user_service.get(db, user.id)

    def blocked(self, user: User) -> bool:
        return user.sign_in_blocked_until is not None and user.sign_in_blocked_until > now()

    async def count_failure(self, db: AsyncSession, user: User) -> None:
        """A wrong password is counted on the account, because the account is what is being guessed at."""
        # The count is raised by the database and not by this side, or attempts arriving together all read the same old value and one of them is lost.
        await db.execute(update(User).where(User.id == user.id).values(failed_sign_ins=User.failed_sign_ins + 1))
        await db.commit()
        await db.refresh(user)

        allowed = settings.security.sign_in_attempts

        if user.failed_sign_ins < allowed:
            return

        waiting = min(settings.security.sign_in_cooldown * 2 ** (user.failed_sign_ins - allowed), settings.security.sign_in_cooldown_max)
        user.sign_in_blocked_until = now() + timedelta(seconds=waiting)

        await db.commit()

    async def authenticate_for_panel(self, db: AsyncSession, login: str, password: str) -> User:
        """The panel belongs to no brand, so it resolves in the global scope, which is the one whoever works in it lives in."""
        user = await self.authenticate(db, None, login, password)

        if user.role not in PANEL_ROLES:
            raise AuthenticationError("error.panel-not-allowed")

        return user

    def ensure_usable(self, user: User) -> None:
        if user.status == UserStatus.BLOCKED:
            raise AuthenticationError("error.account-blocked")

        if user.status == UserStatus.PENDING:
            raise AuthenticationError("error.account-pending")

    async def register(self, db: AsyncSession, brand: Brand, data: dict) -> User:
        """The account is born reading what the person was already reading, so the first e-mail it receives is in that language."""
        payload = dict(data)
        payload["tenant_id"] = brand.id
        payload["role"] = UserRole.NORMAL
        payload["status"] = UserStatus.ACTIVE

        spoken = await language_service.find_by_code(db, current_locale.get())

        if spoken is not None:
            payload.setdefault("language_id", spoken.id)

        return await user_service.create(db, payload)

    async def change_password(self, db: AsyncSession, user: User, current_password: str, new_password: str) -> None:
        if not await verify_password(current_password, user.password_hash):
            raise ValidationError("error.current-password-invalid", "current_password")

        await self.settle_password(user, new_password)
        await db.commit()

    async def settle_password(self, user: User, new_password: str) -> None:
        """A new password ends every session the old one opened, and the epoch is what tells them apart."""
        user.password_hash = await hash_password(new_password)
        user.session_epoch += 1

        # A recovery token is one more way in that the old password asked for, and it ends here too.
        user.recovery_token = None
        user.recovery_token_created_at = None

    async def start_password_reset(self, db: AsyncSession, brand: Brand, login: str) -> None:
        """The token leaves by mail and never in the answer, or knowing an address would be enough to take the account."""
        user = await user_service.find_by_login(db, login, brand.id)

        if user is None or user.email is None or not await self.claim_recovery(db, user):
            return

        await self.mail_recovery(db, brand, user)

    async def claim_recovery(self, db: AsyncSession, user: User) -> bool:
        """Takes the right to write to this address and answers whether this caller got it, because asking again both mails a stranger and burns the token they are holding."""
        moment = now()
        waited = or_(User.recovery_token_created_at.is_(None), User.recovery_token_created_at < moment - timedelta(seconds=settings.password_reset_interval))
        statement = update(User).where(User.id == user.id, waited).values(recovery_token=generate_token(), recovery_token_created_at=moment)
        claimed = (await db.execute(statement)).rowcount == 1

        await db.commit()
        await db.refresh(user)

        return claimed

    async def mail_recovery(self, db: AsyncSession, brand: Brand, user: User) -> None:
        """The code alone is one the site has nowhere to be typed into, and the link is one an application still reads the code out of."""
        link = brand.address(f"/account/reset-password/{user.recovery_token}")

        await email_service.to_user(db, brand.id, user, "email.password-reset-subject", "password_reset", token=user.recovery_token, hours=settings.password_reset_token_ttl // 3600, link=link)

    async def confirm_password_reset(self, db: AsyncSession, token: str, new_password: str) -> None:
        user = await user_service.find_by_recovery_token(db, token)

        if user is None or user.recovery_token_created_at is None:
            raise ValidationError("error.recovery-token-invalid", "token")

        if now() - user.recovery_token_created_at > timedelta(seconds=settings.password_reset_token_ttl):
            raise ValidationError("error.recovery-token-expired", "token")

        await self.settle_password(user, new_password)
        await db.commit()


auth_service = AuthService()
