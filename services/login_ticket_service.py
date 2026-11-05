from datetime import timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from enums.authentication_surface import AuthenticationSurface
from helpers.authentication_error import AuthenticationError
from helpers.authentication_helper import AuthenticationHelper
from helpers.dates import now
from helpers.security import generate_token
from helpers.settings import settings
from helpers.signing import digest
from models.login_ticket import LoginTicket
from models.user import User


class LoginTicketService:
    async def create(self, db: AsyncSession, tenant_id: int | None, user: User, browser: str) -> str:
        token = generate_token()
        ticket = LoginTicket(tenant_id=tenant_id, user_id=user.id, session_epoch=user.session_epoch, token_digest=digest("login-ticket", token), browser_digest=digest("login-browser", browser), expires_at=now() + timedelta(seconds=settings.authentication.ticket_ttl))
        db.add(ticket)
        await db.commit()

        return token

    async def redeem(self, db: AsyncSession, tenant_id: int | None, token: str, browser: str) -> User:
        ticket = await db.scalar(select(LoginTicket).where(LoginTicket.token_digest == digest("login-ticket", token)))

        if ticket is None:
            raise AuthenticationError("error.social-attempt-invalid")

        user_id = ticket.user_id
        epoch = ticket.session_epoch
        moment = now()
        scoped = LoginTicket.tenant_id.is_(None) if tenant_id is None else LoginTicket.tenant_id == tenant_id
        statement = update(LoginTicket).where(scoped, LoginTicket.token_digest == digest("login-ticket", token), LoginTicket.browser_digest == digest("login-browser", browser), LoginTicket.expires_at > moment, LoginTicket.consumed_at.is_(None)).values(consumed_at=moment)
        claimed = (await db.execute(statement)).rowcount == 1
        await db.commit()

        if not claimed:
            raise AuthenticationError("error.social-attempt-invalid")

        user = await db.get(User, user_id, populate_existing=True)

        if user is None or user.session_epoch != epoch:
            raise AuthenticationError("error.social-attempt-invalid")

        return await AuthenticationHelper.signed_in(db, user, AuthenticationSurface.ADMIN, tenant_id)


login_ticket_service = LoginTicketService()
