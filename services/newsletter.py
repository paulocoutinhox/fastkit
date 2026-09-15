from datetime import timedelta
from typing import Callable

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from enums.newsletter import NewsletterStatus
from helpers.brand import Brand
from helpers.dates import now
from helpers.db import insert_or_read
from helpers.i18n import current_locale, translate
from models.newsletter import NewsletterSubscription
from services.crud import CrudService
from services.email import email_service

# How long one address waits before it can be written to again, because asking twice is not a reason to be mailed twice.
INVITATION_INTERVAL = timedelta(hours=1)


class NewsletterSubscriptionService(CrudService):
    """Who hears from a brand, where the address itself is what says so and never a form somebody else filled in."""

    model = NewsletterSubscription
    search_fields = ("email",)
    filter_fields = ("tenant_id", "status", "locale")
    ordering_fields = ("id", "email", "status", "settled_at", "created_at")
    default_ordering = "-id"
    relations = ("tenant",)
    label_fields = ("email",)

    async def subscribe(self, db: AsyncSession, brand: Brand, email: str, link_of: Callable[[str], str]) -> NewsletterSubscription:
        """An address that asks twice is the same row asking twice, and it is written to only after it answers the confirmation."""
        address = email.strip().lower()
        read = select(NewsletterSubscription).where(NewsletterSubscription.tenant_id == brand.id, NewsletterSubscription.email == address)
        settled = await insert_or_read(db, NewsletterSubscription(tenant_id=brand.id, email=address, locale=current_locale.get()), read)

        await db.commit()

        if settled.status == NewsletterStatus.CONFIRMED:
            return settled

        if not await self.claim_invitation(db, settled):
            return settled

        await email_service.queue(db, brand.id, address, translate("email.newsletter-subject"), "newsletter_confirm", locale=settled.locale, link=link_of(settled.token))

        return settled

    async def claim_invitation(self, db: AsyncSession, record: NewsletterSubscription) -> bool:
        """Takes the right to write to this address, and answers whether this caller got it: reading the window and then deciding lets every submit through."""
        moment = now()
        statement = update(NewsletterSubscription).where(NewsletterSubscription.id == record.id, or_(NewsletterSubscription.invited_at.is_(None), NewsletterSubscription.invited_at < moment - INVITATION_INTERVAL)).values(invited_at=moment)
        claimed = (await db.execute(statement)).rowcount == 1

        await db.commit()

        return claimed

    async def find_by_token(self, db: AsyncSession, token: str) -> NewsletterSubscription | None:
        return await db.scalar(select(NewsletterSubscription).where(NewsletterSubscription.token == token))

    async def settle(self, db: AsyncSession, record: NewsletterSubscription, status: NewsletterStatus) -> NewsletterSubscription:
        record.status = status
        record.settled_at = now()

        await db.commit()

        return record


newsletter_subscription_service = NewsletterSubscriptionService()
