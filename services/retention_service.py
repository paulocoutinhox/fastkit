from datetime import timedelta

from sqlalchemy import and_, delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from enums.app_event_status import AppEventStatus
from enums.outbound_email_status import OutboundEmailStatus
from enums.webhook_event_status import WebhookEventStatus
from helpers.cache import store as cache_store
from helpers.dates import now
from helpers.scheduler import store
from helpers.settings import settings
from models.app_event import AppEvent
from models.banner_impression import BannerImpression
from models.client_request import ClientRequest
from models.email_login_challenge import EmailLoginChallenge
from models.login_ticket import LoginTicket
from models.outbound_email import OutboundEmail
from models.social_login_attempt import SocialLoginAttempt
from models.system_log import SystemLog
from models.webhook_event import WebhookEvent
from services.app_event_service import MAX_ATTEMPTS as EVENT_ATTEMPTS
from services.email_service import MAX_ATTEMPTS as EMAIL_ATTEMPTS
from services.webhook_service import MAX_ATTEMPTS as WEBHOOK_ATTEMPTS


class RetentionService:
    """What an operational table stops keeping, so an instance that runs for years is one that still answers."""

    def settled(self) -> list[tuple[str, type, int, object]]:
        """A row is only dropped once nothing will ever act on it again, and a table with no window keeps everything."""
        spent_events = and_(AppEvent.status == AppEventStatus.FAILED, AppEvent.attempts >= EVENT_ATTEMPTS)
        spent_notices = and_(WebhookEvent.status == WebhookEventStatus.FAILED, WebhookEvent.attempts >= WEBHOOK_ATTEMPTS)
        spent_messages = and_(OutboundEmail.status == OutboundEmailStatus.FAILED, OutboundEmail.attempts >= EMAIL_ATTEMPTS)

        return [
            ("email_login_challenge", EmailLoginChallenge, settings.retention.authentication_days, EmailLoginChallenge.expires_at < now()),
            ("social_login_attempt", SocialLoginAttempt, settings.retention.authentication_days, SocialLoginAttempt.expires_at < now()),
            ("login_ticket", LoginTicket, settings.retention.authentication_days, LoginTicket.expires_at < now()),
            ("system_log", SystemLog, settings.retention.system_log_days, None),
            ("app_event", AppEvent, settings.retention.app_event_days, or_(AppEvent.status.in_((AppEventStatus.PROCESSED, AppEventStatus.IGNORED)), spent_events)),
            ("webhook_event", WebhookEvent, settings.retention.webhook_event_days, or_(WebhookEvent.status.in_((WebhookEventStatus.COMPLETED, WebhookEventStatus.IGNORED)), spent_notices)),
            ("outbound_email", OutboundEmail, settings.retention.outbound_email_days, or_(OutboundEmail.status.in_((OutboundEmailStatus.SENT, OutboundEmailStatus.REFUSED)), spent_messages)),
            # A key holds the answer a repeat is handed back, and past the window no client is still repeating that call.
            ("client_request", ClientRequest, settings.retention.client_request_days, ClientRequest.answer.is_not(None)),
            # The row is what keeps one visitor from counting twice in a day, so past the window nothing reads it again.
            ("banner_impression", BannerImpression, settings.retention.banner_impression_days, None),
        ]

    async def discard(self, db: AsyncSession) -> dict:
        discarded = {}

        for name, model, days, settled in self.settled():
            if days > 0:
                discarded[name] = await self.trim(db, model, now() - timedelta(days=days), settled)

        discarded["cron_run"] = await self.purge_runs()
        discarded["cache_entry"] = await self.purge_answers()

        return discarded

    async def trim(self, db: AsyncSession, model, before, settled) -> int:
        """A row is dropped once it is older than the window and nothing will act on it again."""
        return await self.trim_where(db, model, model.created_at < before if settled is None else and_(model.created_at < before, settled))

    async def trim_where(self, db: AsyncSession, model, condition) -> int:
        """The delete walks a page at a time, because the first pass of a table nobody trimmed would hold a lock for minutes."""
        removed = 0

        while True:
            ids = list((await db.execute(select(model.id).where(condition).order_by(model.id.asc()).limit(settings.retention.batch))).scalars())

            if not ids:
                return removed

            removed += (await db.execute(delete(model).where(model.id.in_(ids)))).rowcount
            await db.commit()

    async def purge_runs(self) -> int:
        """The queue writes one row per occurrence of every task, and nothing ever reads a settled one again."""
        if settings.retention.cron_run_days <= 0:
            return 0

        return await self.drained(store.purge, now() - timedelta(days=settings.retention.cron_run_days))

    async def purge_answers(self) -> int:
        """A cached answer is dead the moment it goes stale, and nothing is ever served from it again."""
        return await self.drained(cache_store.purge, now())

    async def drained(self, purge, before) -> int:
        """Both libraries delete one batch per call, so a day that wrote more than a batch is emptied by calling again until nothing is left."""
        removed = 0

        while gone := await purge(before, settings.retention.batch):
            removed += gone

        return removed


retention_service = RetentionService()
