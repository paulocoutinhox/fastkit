import logging

from sqlalchemy import and_, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from enums.event import AppEventName, AppEventStatus
from enums.system_log import LogCategory, LogLevel
from helpers.brand import Brand
from helpers.dates import now
from helpers.db import insert_or_read
from models.event import AppEvent
from models.user import User
from services.crud import CrudService
from services.delivery import ABANDONED_AFTER
from services.system_log import system_log_service

# An event that keeps failing stops being retried, or it would hold a slot of every pass forever.
MAX_ATTEMPTS = 5

# What a reported event becomes on the system log, and the names left out are the ones this side has nothing to do about.
EVENT_CATEGORIES = {AppEventName.CHECKOUT_STARTED: LogCategory.PURCHASE, AppEventName.PRODUCT_PURCHASED: LogCategory.PURCHASE, AppEventName.CONTENT_VIEWED: LogCategory.CONTENT, AppEventName.GALLERY_VIEWED: LogCategory.CONTENT}

logger = logging.getLogger(__name__)


class AppEventService(CrudService):
    model = AppEvent
    search_fields = ("uuid", "name")
    filter_fields = ("tenant_id", "user_id", "status", "name")
    ordering_fields = ("id", "name", "status", "occurred_at", "created_at")
    default_ordering = "-id"
    relations = ("tenant", "user")
    label_fields = ("name",)

    async def ingest(self, db: AsyncSession, brand: Brand, user: User | None, events: list[dict]) -> tuple[int, int]:
        """A batch is replayed whenever the app loses connectivity, so a UUID already stored is counted as duplicated."""
        incoming = {event["uuid"]: event for event in events}

        known = await self.known_uuids(db, list(incoming))
        accepted = 0

        for uuid, event in incoming.items():
            if uuid in known:
                continue

            record = AppEvent(tenant_id=brand.id, user_id=user.id if user else None, uuid=uuid, name=event["name"], params=event["params"], occurred_at=event["occurred_at"], status=AppEventStatus.PENDING)

            if await insert_or_read(db, record, select(AppEvent).where(AppEvent.uuid == uuid)) is record:
                accepted += 1

        await self.persist(db)

        return accepted, len(incoming) - accepted

    async def known_uuids(self, db: AsyncSession, uuids: list[str]) -> set[str]:
        return set((await db.execute(select(AppEvent.uuid).where(AppEvent.uuid.in_(uuids)))).scalars())

    async def claim(self, db: AsyncSession, record_id: int) -> bool:
        """Takes an event for this pass, and answers whether it was the one that got it: a pass running past the interval overlaps the next."""
        takeable = or_(AppEvent.status.in_((AppEventStatus.PENDING, AppEventStatus.FAILED)), and_(AppEvent.status == AppEventStatus.PROCESSING, AppEvent.updated_at < now() - ABANDONED_AFTER))
        statement = update(AppEvent).where(AppEvent.id == record_id, takeable, AppEvent.attempts < MAX_ATTEMPTS).values(status=AppEventStatus.PROCESSING, attempts=AppEvent.attempts + 1)
        claimed = (await db.execute(statement)).rowcount == 1

        await db.commit()

        return claimed

    async def process_pending(self, db: AsyncSession, limit: int = 200) -> list[AppEvent]:
        """An event that nobody reads is still closed, so the queue drains instead of growing behind one name the backend never learned."""
        # What broke is read again on the next pass, like every other queue here, and the attempts are what keep one from being read forever.
        abandoned = and_(AppEvent.status == AppEventStatus.PROCESSING, AppEvent.updated_at < now() - ABANDONED_AFTER)
        statement = select(AppEvent.id).where(or_(AppEvent.status.in_((AppEventStatus.PENDING, AppEventStatus.FAILED)), abandoned), AppEvent.attempts < MAX_ATTEMPTS).order_by(AppEvent.id.asc()).limit(limit)
        worked = []

        for record_id in (await db.execute(statement)).scalars():
            if not await self.claim(db, record_id):
                continue

            event = await db.get(AppEvent, record_id)

            try:
                event.status = AppEventStatus.PROCESSED if await self.dispatch(db, event) else AppEventStatus.IGNORED
                event.error_code = None
                event.error_message = None
            except Exception as error:
                logger.exception("[events] %s failed", event.uuid)

                event.status = AppEventStatus.FAILED
                event.error_code = type(error).__name__
                event.error_message = str(error)

            event.processed_at = now()
            await db.commit()

            worked.append(event)

        return worked

    async def dispatch(self, db: AsyncSession, event: AppEvent) -> bool:
        """Answers whether anything on this side read the event, which is what separates one that was processed from one that was ignored."""
        category = EVENT_CATEGORIES.get(event.name)

        if category is None:
            return False

        await system_log_service.record(db, event.tenant_id, event.user_id, LogLevel.INFO, category, event.name, event.params)

        return True


app_event_service = AppEventService()
