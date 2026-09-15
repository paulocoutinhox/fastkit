from datetime import timedelta
from urllib.parse import quote

from sqlalchemy import case, func, or_, update
from sqlalchemy.ext.asyncio import AsyncSession

from enums.user import PANEL_ROLES, UserRole, UserStatus
from helpers.brand import Brand
from helpers.dates import now
from helpers.db import refusing
from helpers.errors import AuthenticationError, ValidationError
from helpers.i18n import current_locale
from helpers.security import generate_token, hash_password, no_such_account, verify_password
from helpers.settings import settings
from models.user import User
from services.email import email_service
from services.language import language_service
from services.tenant import tenant_service
from services.user import user_service


def awaiting():
    """The accounts a confirmation letter still answers for: one waiting to open, and one waiting on a new address."""
    return or_(User.status == UserStatus.PENDING, User.pending_email.is_not(None))


class AuthService:
    """Everything that turns a person into a session, where the token never expires so what gates access is the account status."""

    async def authenticate(self, db: AsyncSession, tenant_id: int | None, login: str, password: str) -> User:
        return await self.settle_sign_in(db, await user_service.find_by_login(db, login, tenant_id), password)

    async def settle_sign_in(self, db: AsyncSession, user: User | None, password: str) -> User:
        """The password is always checked against a hash, whoever was found, so the time of the answer never says whether an account exists."""
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

    async def authenticate_for_panel(self, db: AsyncSession, tenant_id: int | None, login: str, password: str) -> User:
        """The panel is opened on the domain of a brand, so it answers the operators of that brand and the ones of no brand, who reach every one."""
        user = await self.settle_sign_in(db, await user_service.find_operator(db, login, tenant_id), password)

        if user.role not in PANEL_ROLES:
            raise AuthenticationError("error.panel-not-allowed")

        return user

    def ensure_usable(self, user: User) -> None:
        if user.status == UserStatus.BLOCKED:
            raise AuthenticationError("error.account-blocked")

        if user.status == UserStatus.PENDING:
            raise AuthenticationError("error.account-pending")

    async def register(self, db: AsyncSession, brand: Brand, data: dict, wanted: str = "") -> User:
        """The account is born reading what the person was already reading, so the first e-mail it receives is in that language."""
        payload = dict(data)
        payload["tenant_id"] = brand.id
        payload["role"] = UserRole.NORMAL

        # An account that has to prove its address is born unable to answer, and the guard that reads the status is what keeps it that way.
        payload["status"] = UserStatus.PENDING if self.confirmation_is_asked_of(payload.get("email")) else UserStatus.ACTIVE

        spoken = await language_service.find_by_code(db, current_locale.get())

        if spoken is not None and payload.get("language_id") is None:
            payload["language_id"] = spoken.id

        user = await user_service.create(db, payload)

        if user.status == UserStatus.PENDING:
            await self.mail_confirmation(db, brand, user, wanted)

        return user

    def confirmation_is_asked_of(self, email: str | None) -> bool:
        """An account is created with any one of four identities, so one without an address has nowhere to be written to and nothing to prove."""
        return settings.confirm_sign_up and bool(email)

    async def mail_confirmation(self, db: AsyncSession, brand: Brand, user: User, wanted: str = "") -> None:
        """Writes the address the one letter that proves it, and only where this caller took the window: the account's own while it waits to open, and the new one while it waits to replace it."""
        if not await self.claim_confirmation(db, user):
            return

        link = self.onward(brand, f"/account/confirm/{user.confirmation_token}", wanted)

        if user.pending_email is not None:
            await email_service.to_user(db, brand.id, user, "email.confirm-address-subject", "address_confirmation", address=user.pending_email, token=user.confirmation_token, link=link)

            return

        await email_service.to_user(db, brand.id, user, "email.confirm-sign-up-subject", "account_confirmation", token=user.confirmation_token, link=link)

    async def settle_account(self, db: AsyncSession, user: User, data: dict) -> User:
        """What an account writes about itself, where a new address waits for that address to answer before it replaces the one the account proved, and the letter is written by the account's own brand."""
        written = dict(data)
        address = written.get("email")
        moved = self.confirmation_is_asked_of(address) and address.lower() not in (user.email, user.pending_email)

        # The address already waiting is the one its letter is out for, so sending it again changes nothing and draws no second letter.
        if address and address.lower() == user.pending_email:
            written.pop("email")

        if moved:
            await user_service.ensure_free(db, "email", address, user.tenant_id, user)
            written.pop("email")
            # A letter already out was written for another address, so it stops answering for this one even when the window holds the next letter back.
            written |= {"pending_email": address.lower(), "confirmation_token": None}

        updated = await user_service.update(db, user.id, written)

        if moved:
            await self.mail_confirmation(db, await tenant_service.brand_of(db, user.tenant_id), updated)

        return updated

    def onward(self, brand: Brand, path: str, wanted: str) -> str:
        """Where the person was going is written into the link because the letter is the only thing that crosses the wait, and it may be opened on another device days later."""
        return brand.address(f"{path}?next={quote(wanted, safe='')}" if wanted else path)

    async def claim_confirmation(self, db: AsyncSession, user: User) -> bool:
        """Takes the right to write to this address and answers whether this caller got it, and the token is drawn again with the window so that only the last letter sent still opens the account it names."""
        moment = now()
        waited = or_(User.confirmation_sent_at.is_(None), User.confirmation_sent_at < moment - timedelta(seconds=settings.confirm_sign_up_interval))
        statement = update(User).where(User.id == user.id, awaiting(), waited).values(confirmation_token=generate_token(), confirmation_sent_at=moment)
        claimed = (await db.execute(statement)).rowcount == 1

        await db.commit()
        await db.refresh(user)

        return claimed

    async def resend_confirmation(self, db: AsyncSession, brand: Brand, login: str) -> None:
        """An address that never got the letter has no other way back in, and a login nobody has answers exactly like one that is already confirmed."""
        user = await user_service.find_by_login(db, login, brand.id)

        if user is None or not (user.status == UserStatus.PENDING and user.email or user.pending_email):
            return

        await self.mail_confirmation(db, brand, user)

    async def awaiting_confirmation(self, db: AsyncSession, tenant_id: int | None, token: str) -> User | None:
        """The account a confirmation link still opens, which is one of this brand waiting on its address with that very token."""
        user = await user_service.find_by_confirmation_token(db, token, tenant_id)

        return user if user is not None and (user.status == UserStatus.PENDING or user.pending_email is not None) else None

    async def confirm_sign_up(self, db: AsyncSession, tenant_id: int | None, token: str) -> tuple[User, bool]:
        """The token is the address saying it is the address, and it answers whether this letter opened the account, which is the only case where holding it starts a session."""
        user = await self.awaiting_confirmation(db, tenant_id, token)

        if user is None:
            raise ValidationError("error.confirmation-token-invalid", "token")

        # An account that is already open was proved by another identity, and whoever holds a letter to a mistyped address is not its owner.
        opened = user.status == UserStatus.PENDING

        # The write is conditioned on the token too, so a letter a newer one replaced opens nothing, and the token goes with the status so the same link never opens an account twice.
        # An address the account wrote later replaces the one it holds, and one somebody else proved first in the meantime is a collision the index refuses.
        settled = (
            update(User).where(User.id == user.id, awaiting(), User.confirmation_token == token).values(status=case((User.status == UserStatus.PENDING, UserStatus.ACTIVE), else_=User.status), email=func.coalesce(User.pending_email, User.email), pending_email=None, confirmation_token=None, confirmation_sent_at=None)
        )

        async with refusing(db, "error.email-already-used"):
            if (await db.execute(settled)).rowcount != 1:
                await db.rollback()

                raise ValidationError("error.confirmation-token-invalid", "token")

        await db.commit()
        await db.refresh(user)

        return user, opened

    async def change_password(self, db: AsyncSession, user: User, current_password: str, new_password: str) -> None:
        if not await verify_password(current_password, user.password_hash):
            raise ValidationError("error.current-password-invalid", "current_password")

        await self.settle_password(db, user, new_password)

    async def settle_password(self, db: AsyncSession, user: User, new_password: str) -> None:
        """A new password ends every session the old one opened, and the epoch is what tells them apart."""
        # A recovery token is one more way in that the old password asked for, and it ends here too.
        # The epoch is raised by the database: two changes that crossed would read the same number and write the same one, leaving both sessions alive.
        settled = update(User).where(User.id == user.id).values(password_hash=await hash_password(new_password), session_epoch=User.session_epoch + 1, recovery_token=None, recovery_token_created_at=None)

        await db.execute(settled)
        await db.commit()

        # The caller mints a token out of this row, so it reads the epoch the database wrote and never the one it came in with.
        await db.refresh(user)

    async def start_password_reset(self, db: AsyncSession, brand: Brand, login: str, wanted: str = "") -> None:
        """The token leaves by mail and never in the answer, or knowing an address would be enough to take the account."""
        user = await user_service.find_by_login(db, login, brand.id)

        if user is None or user.email is None or not await self.claim_recovery(db, user):
            return

        await self.mail_recovery(db, brand, user, wanted)

    async def claim_recovery(self, db: AsyncSession, user: User) -> bool:
        """Takes the right to write to this address and answers whether this caller got it, because asking again both mails a stranger and burns the token they are holding."""
        moment = now()
        waited = or_(User.recovery_token_created_at.is_(None), User.recovery_token_created_at < moment - timedelta(seconds=settings.password_reset_interval))
        statement = update(User).where(User.id == user.id, waited).values(recovery_token=generate_token(), recovery_token_created_at=moment)
        claimed = (await db.execute(statement)).rowcount == 1

        await db.commit()
        await db.refresh(user)

        return claimed

    async def mail_recovery(self, db: AsyncSession, brand: Brand, user: User, wanted: str) -> None:
        """The code alone is one the site has nowhere to be typed into, and the link is one an application still reads the code out of."""
        link = self.onward(brand, f"/account/reset-password/{user.recovery_token}", wanted)

        await email_service.to_user(db, brand.id, user, "email.password-reset-subject", "password_reset", token=user.recovery_token, hours=settings.password_reset_token_ttl // 3600, link=link)

    async def recoverable(self, db: AsyncSession, tenant_id: int | None, token: str) -> User:
        """The account of this brand a recovery link still opens, refused when the link was spent, replaced or left to expire."""
        user = await user_service.find_by_recovery_token(db, token, tenant_id)

        if user is None or user.recovery_token_created_at is None:
            raise ValidationError("error.recovery-token-invalid", "token")

        if now() - user.recovery_token_created_at > timedelta(seconds=settings.password_reset_token_ttl):
            raise ValidationError("error.recovery-token-expired", "token")

        return user

    async def confirm_password_reset(self, db: AsyncSession, tenant_id: int | None, token: str, new_password: str) -> None:
        user = await self.recoverable(db, tenant_id, token)

        # The token is spent before the password is written, so two calls holding it cannot both set one and both walk in with a session.
        # Answering the letter proves the address, so an account waiting on it opens and one locked by guessing is let in, while one an operator blocked stays blocked.
        spent = (
            update(User)
            .where(User.id == user.id, User.recovery_token == token)
            .values(recovery_token=None, recovery_token_created_at=None, status=case((User.status == UserStatus.PENDING, UserStatus.ACTIVE), else_=User.status), confirmation_token=None, confirmation_sent_at=None, failed_sign_ins=0, sign_in_blocked_until=None)
        )

        if (await db.execute(spent)).rowcount != 1:
            await db.commit()

            raise ValidationError("error.recovery-token-invalid", "token")

        await db.commit()
        await self.settle_password(db, user, new_password)


auth_service = AuthService()
