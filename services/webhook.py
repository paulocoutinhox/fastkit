"""What a gateway reported, written down before it is read, and what it moves once it is."""

import hashlib
import json

import httpx
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from enums.integration import WebhookEventStatus
from enums.system_log import LogCategory, LogLevel
from helpers.dates import now
from helpers.db import insert_or_read
from models.commerce import Purchase
from models.integration import ExternalProduct, Integration, WebhookEvent
from models.subscription import Subscription
from models.user import User
from services.commerce import commerce_service, purchase_service
from services.delivery import ABANDONED_AFTER
from services.gateway import PROVIDERS, SUBSCRIBER_TIMEOUT, InboundCall, ProviderEvent
from services.integration import integration_service
from services.reconciliation import reconciliation_service
from services.system_log import system_log_service

# An event that keeps failing stops being retried, or it would hold a slot of every pass forever.
MAX_ATTEMPTS = 5


class WebhookService:
    """An event is a trigger and never a truth: it says which account to look at, and what the provider answers is what gets written."""

    async def find_integration(self, db: AsyncSession, key: str) -> Integration | None:
        return await db.scalar(select(Integration).where(Integration.webhook_key == key, Integration.active.is_(True)))

    async def ingest(self, db: AsyncSession, integration: Integration, call: InboundCall) -> WebhookEvent:
        provider = PROVIDERS[integration.provider]

        # The secret is read here and handed over, so a gateway is a class that never reaches back into a service.
        provider.authenticate(integration, call, integration_service.read_webhook_secret(integration))

        async with httpx.AsyncClient(timeout=SUBSCRIBER_TIMEOUT) as client:
            event = await provider.read(integration, call, client)

        if event is None:
            return await self.unread(db, integration, call)

        record = await self.record_of(db, integration, event, call)

        if record.status in (WebhookEventStatus.COMPLETED, WebhookEventStatus.IGNORED):
            return record

        return await self.run(db, integration, event, record)

    async def run(self, db: AsyncSession, integration: Integration, event: ProviderEvent, record: WebhookEvent) -> WebhookEvent:
        record.attempts += 1
        record.status = WebhookEventStatus.PROCESSING
        marks = (record.id, integration.tenant_id, integration.provider)
        await db.commit()

        try:
            await self.apply(db, integration, event, record)
            await db.commit()
        except Exception as error:
            await db.rollback()
            await self.fail(db, marks, error)

            raise

        return record

    async def apply(self, db: AsyncSession, integration: Integration, event: ProviderEvent, record: WebhookEvent) -> None:
        # A payment is settled before an account is asked for, because a charge names no account of ours and the purchase it moves says whose it is.
        settled = await self.settle_payment(db, integration, event)
        user = await self.user_of(db, integration, event)

        if user is None and settled is None:
            record.status = WebhookEventStatus.IGNORED
            record.error_code = "unresolved"
            record.error_message = f"no account of this tenant answers for {event.account_token}"

            return

        if user is not None:
            provider = PROVIDERS[integration.provider]

            if not provider.event_stated:
                await reconciliation_service.reconcile_account(db, integration, user)
            elif event.state is not None:
                # A notice is about one purchase, so what else the account holds is not closed by the silence of this one.
                await reconciliation_service.apply(db, integration, user, list(event.state), complete=False)
                await db.commit()

            record.subscription_id = await self.subscription_of(db, integration, user, event)

        record.user_id = user.id if user is not None else settled.user_id
        record.status = WebhookEventStatus.COMPLETED
        record.processed_at = now()

    async def settle_payment(self, db: AsyncSession, integration: Integration, event: ProviderEvent) -> Purchase | None:
        """The reference is a row of this database, so resolving it is the work of a service and never of a gateway."""
        if event.purchase_status is None:
            return None

        purchase = await self.purchase_of(db, integration, event)

        if purchase is None:
            return None

        return await commerce_service.settle_purchase(db, purchase, event.purchase_status, event.payment_id)

    async def purchase_of(self, db: AsyncSession, integration: Integration, event: ProviderEvent) -> Purchase | None:
        """A session names the reference this side minted, and a charge names only the payment stored when that session settled."""
        if event.reference:
            found = await purchase_service.find_by_reference(db, event.reference)
        elif event.payment_id:
            found = await purchase_service.find_by_payment(db, event.payment_id)
        else:
            return None

        # The key that named it belongs to the gateway that called, and a purchase opened through another one is not this notice to move.
        return found if found is not None and found.integration_id == integration.id else None

    async def subscription_of(self, db: AsyncSession, integration: Integration, user: User, event: ProviderEvent) -> int | None:
        """What the money moved is read from the product the event names, so the statement of a subscription is only its own."""
        if not event.product_reference:
            return None

        statement = select(Subscription.id).join(ExternalProduct, ExternalProduct.id == Subscription.external_product_id).where(Subscription.integration_id == integration.id, Subscription.user_id == user.id, ExternalProduct.external_id == event.product_reference)

        return await db.scalar(statement)

    async def user_of(self, db: AsyncSession, integration: Integration, event: ProviderEvent) -> User | None:
        if not event.account_token:
            return None

        return await db.scalar(select(User).where(User.token == event.account_token, User.tenant_id == integration.tenant_id))

    async def retry_failed(self, db: AsyncSession, limit: int = 100) -> list[WebhookEvent]:
        """A gateway gives up after a handful of tries, and a node that died mid-flight leaves a row nobody would ever look at again."""
        abandoned = and_(WebhookEvent.status == WebhookEventStatus.PROCESSING, WebhookEvent.updated_at < now() - ABANDONED_AFTER)
        statement = select(WebhookEvent.id).where(or_(WebhookEvent.status == WebhookEventStatus.FAILED, abandoned), WebhookEvent.attempts < MAX_ATTEMPTS).order_by(WebhookEvent.created_at.asc()).limit(limit)
        stuck = list((await db.execute(statement)).scalars())
        done = []

        async with httpx.AsyncClient(timeout=SUBSCRIBER_TIMEOUT) as client:
            # One row falling over again rolls the session back, so the next is read here instead of held across it.
            for record_id in stuck:
                record = await db.get(WebhookEvent, record_id)
                integration = await db.get(Integration, record.integration_id)
                call = InboundCall(method="POST", headers={"content-type": "application/json"}, body=json.dumps(record.payload).encode())
                event = await PROVIDERS[integration.provider].read(integration, call, client)

                # The mark is written now, because a row falling over further down rolls the session back and would take it with it.
                if event is None:
                    record.status = WebhookEventStatus.IGNORED
                    await db.commit()

                    continue

                try:
                    await self.run(db, integration, event, record)
                    done.append(record)
                except Exception:
                    # Run already wrote the failure on the record, and one that keeps failing must not hold the sweep behind it.
                    continue

        return done

    async def fail(self, db: AsyncSession, marks: tuple, error: Exception) -> None:
        record_id, tenant_id, provider = marks
        record = await db.get(WebhookEvent, record_id)

        record.status = WebhookEventStatus.FAILED
        record.error_code = type(error).__name__
        record.error_message = str(error)

        await system_log_service.record(db, tenant_id, record.user_id, LogLevel.ERROR, LogCategory.PURCHASE, f"webhook event {record.external_event_id} of {provider} failed", {"webhook_event_id": record.id, "error": str(error)})
        await db.commit()

    async def unread(self, db: AsyncSession, integration: Integration, call: InboundCall) -> WebhookEvent:
        """A call nobody here knows how to read is still written down, because losing what arrived is worse than not reading it."""
        digest = self.digest(call)
        record = WebhookEvent(tenant_id=integration.tenant_id, integration_id=integration.id, external_event_id=digest, payload_hash=digest, error_code="unread", status=WebhookEventStatus.IGNORED, payload=call.data() or {"body": call.text()}, meta=call.recorded())

        return await self.store(db, record)

    async def record_of(self, db: AsyncSession, integration: Integration, event: ProviderEvent, call: InboundCall) -> WebhookEvent:
        """The provider resends what it is unsure about, so the same event id is the same row and never a second reading."""
        digest = self.digest(call)
        external_event_id = event.external_event_id or digest
        existing = await db.scalar(select(WebhookEvent).where(WebhookEvent.integration_id == integration.id, WebhookEvent.external_event_id == external_event_id))

        if existing is not None:
            return existing

        record = WebhookEvent(
            tenant_id=integration.tenant_id, integration_id=integration.id, external_event_id=external_event_id, payload_hash=digest, action=event.action, payload=call.data(), amount=event.amount, currency=event.currency, occurred_at=event.occurred_at, status=WebhookEventStatus.RECEIVED, meta=call.recorded()
        )

        return await self.store(db, record)

    async def store(self, db: AsyncSession, record: WebhookEvent) -> WebhookEvent:
        """Two deliveries of one event can race past the read, and the event id is what settles it."""
        settled = await insert_or_read(db, record, select(WebhookEvent).where(WebhookEvent.integration_id == record.integration_id, WebhookEvent.external_event_id == record.external_event_id))
        await db.commit()

        return settled

    def digest(self, call: InboundCall) -> str:
        return hashlib.sha256(call.method.encode() + b"|" + json.dumps(call.query, sort_keys=True).encode() + b"|" + call.body).hexdigest()


webhook_service = WebhookService()
