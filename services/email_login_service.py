import hmac
import secrets
from datetime import timedelta

from sqlalchemy import case, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from enums.authentication_surface import AuthenticationSurface
from enums.user import PANEL_ROLES
from enums.user_role import UserRole
from enums.user_status import UserStatus
from helpers.authentication_error import AuthenticationError
from helpers.authentication_helper import AuthenticationHelper
from helpers.brand import Brand
from helpers.dates import now
from helpers.db import insert_or_read
from helpers.i18n import current_locale, translate
from helpers.scope import belongs_to_tenant
from helpers.security import generate_token
from helpers.settings import settings
from helpers.signing import digest
from helpers.validation_error import ValidationError
from models.email_login_challenge import EmailLoginChallenge
from models.user import User
from services.email_service import email_service
from services.user_service import user_service

# The longest a letter is held back, which is where the wait that doubles with every spent code stops.
RESEND_WAIT_MAX = timedelta(days=1)

# Doubling the shortest interval this many times already passes a day, so counting further only grows a number nobody reads.
DOUBLINGS_MAX = 12


class EmailLoginService:
    async def request(self, db: AsyncSession, brand: Brand, email: str, surface: AuthenticationSurface) -> EmailLoginChallenge:
        AuthenticationHelper.require_email(surface)

        configuration = settings.authentication.email
        moment = now()
        address = email.lower()
        scope_key = digest("email-login-scope", f"{brand.id}:{surface.value}:{address}")
        token = generate_token()
        code = f"{secrets.randbelow(1_000_000):06d}"
        changes = {"token": token, "code_digest": digest("email-login-code", f"{token}:{code}"), "attempts": 0, "expires_at": moment + timedelta(seconds=configuration.code_ttl), "resend_at": moment + self.resend_wait(0), "consumed_at": None}
        proposed = EmailLoginChallenge(tenant_id=brand.id, surface=surface, email=address, scope_key=scope_key, **changes)
        challenge = await insert_or_read(db, proposed, select(EmailLoginChallenge).where(EmailLoginChallenge.scope_key == scope_key))

        if challenge is not proposed:
            # The wait is read off the wrong codes this address already took, and the write holds only while nobody typed another since that read.
            failures = challenge.failures
            replaced = update(EmailLoginChallenge).where(EmailLoginChallenge.id == challenge.id, EmailLoginChallenge.resend_at <= moment, EmailLoginChallenge.failures == failures).values({**changes, "resend_at": moment + self.resend_wait(failures)})
            claimed = (await db.execute(replaced)).rowcount == 1

            if not claimed:
                await db.commit()
                await db.refresh(challenge)

                if challenge.consumed_at is not None or challenge.expires_at <= moment or challenge.attempts >= configuration.max_attempts:
                    seconds = max(1, int((challenge.resend_at - moment).total_seconds()) + 1)

                    raise ValidationError("error.sign-in-code-wait", "email", seconds=seconds)

                return challenge

        await email_service.queue(db, brand.id, address, translate("email.sign-in-code-subject"), "sign-in-code", locale=current_locale.get(), code=code, minutes=configuration.code_ttl // 60)
        await db.refresh(challenge)

        return challenge

    def resend_wait(self, failures: int) -> timedelta:
        """How long the next letter waits, which doubles with every code the address spent on wrong guesses, because a new letter is otherwise five new guesses a minute for as long as anybody keeps asking."""
        configuration = settings.authentication.email
        spent = min(failures // configuration.max_attempts, DOUBLINGS_MAX)

        return min(RESEND_WAIT_MAX, timedelta(seconds=configuration.resend_interval * 2**spent))

    async def confirm(self, db: AsyncSession, brand: Brand, token: str, code: str, surface: AuthenticationSurface) -> User:
        AuthenticationHelper.require_email(surface)

        configuration = settings.authentication.email
        moment = now()
        live = (EmailLoginChallenge.token == token, belongs_to_tenant(EmailLoginChallenge.tenant_id, brand.id), EmailLoginChallenge.surface == surface, EmailLoginChallenge.consumed_at.is_(None), EmailLoginChallenge.expires_at > moment, EmailLoginChallenge.attempts < configuration.max_attempts)
        expected = digest("email-login-code", f"{token}:{code}")

        # Counting the attempt and spending the code are one write, so guesses sent together wait on the same row and the ceiling holds whatever the concurrency.
        right = EmailLoginChallenge.code_digest == expected
        attempt = update(EmailLoginChallenge).where(*live).values(attempts=EmailLoginChallenge.attempts + 1, failures=case((right, 0), else_=EmailLoginChallenge.failures + 1), consumed_at=case((right, moment), else_=None))
        counted = (await db.execute(attempt)).rowcount == 1
        await db.commit()

        challenge = await db.scalar(select(EmailLoginChallenge).where(EmailLoginChallenge.token == token).execution_options(populate_existing=True))

        # A letter asked for again between the two statements replaces the challenge, and the code of the replaced one opens nothing.
        if not counted or challenge is None or not hmac.compare_digest(challenge.code_digest, expected):
            raise ValidationError("error.sign-in-code-invalid", "code")

        user = await AuthenticationHelper.by_email(db, brand.id, challenge.email, surface)

        if user is None:
            if surface == AuthenticationSurface.ADMIN:
                await db.commit()

                raise AuthenticationError("error.panel-not-allowed")

            await user_service.ensure_free(db, "email", challenge.email, brand.id, None)

            proposed = User(tenant_id=brand.id, email=challenge.email, password_hash="", role=UserRole.NORMAL, status=UserStatus.ACTIVE)
            user = await insert_or_read(db, proposed, select(User).where(User.email == challenge.email, belongs_to_tenant(User.tenant_id, brand.id)))

        # The panel opens only to an operator, so an account of a reader is refused before anything about it is changed.
        if surface == AuthenticationSurface.ADMIN and user.role not in PANEL_ROLES:
            raise AuthenticationError("error.panel-not-allowed")

        if user.status == UserStatus.PENDING:
            await db.execute(update(User).where(User.id == user.id, User.status == UserStatus.PENDING).values(status=UserStatus.ACTIVE, password_hash="", session_epoch=User.session_epoch + 1, confirmation_token=None, confirmation_sent_at=None, recovery_token=None, recovery_token_created_at=None))
            await db.refresh(user)

        await db.commit()

        return await AuthenticationHelper.signed_in(db, user, surface, brand.id)


email_login_service = EmailLoginService()
