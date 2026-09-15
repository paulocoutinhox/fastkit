import asyncio
import logging
from datetime import timedelta

import httpx
from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from enums.subscription import CLOSED_SUBSCRIPTION_STATUSES, ELIGIBLE_SUBSCRIPTION_STATUSES, BenefitStatus, ResumeDeliveryPolicy, SubscriptionStatus
from enums.system_log import LogCategory, LogLevel
from helpers.dates import now
from helpers.db import insert_or_read
from models.integration import ExternalProduct, Integration
from models.subscription import Plan, Subscription
from models.user import User
from services.delivery import delivery_service
from services.gateway import PROVIDERS, ProviderPurchase, RateLimited
from services.integration import integration_service
from services.system_log import system_log_service

# RevenueCat publishes no limit for the v1 rest API and recommends about one call a second, so that recommendation is the ceiling and the sweep takes a quarter of it.
PROVIDER_BUDGET = 60

SWEEP_SHARE = 0.25

PACE = 60 / (PROVIDER_BUDGET * SWEEP_SHARE)

# The sweep is the first of five steps of one pass, so it spends a share of the pass and the four that follow it keep the rest.
SWEEP_WINDOW = timedelta(minutes=3)

SWEEP_LIMIT = int(SWEEP_WINDOW.total_seconds() / PACE)

TIMEOUT = 10.0

# An account read this recently is not asked about again, so a client in a loop never becomes a flood of calls.
COOLDOWN = timedelta(seconds=10)

# A renewal whose event was lost is only found by asking again after the clock already closed the subscription.
RECENTLY_CLOSED = timedelta(days=2)

# A key that is rejected is a configuration to fix and never a blip to wait out, so it is reported instead of retried in silence.
REFUSED = (401, 403)

logger = logging.getLogger(__name__)


class Unreadable(Exception):
    """The gateway cannot be read — no key, or a key it refuses — and answering zero would read as a purchase that was handled."""


class ReconciliationService:
    """The store owns the purchase and we own the account: what the provider answers is the state, and this is the only place that writes it."""

    async def reconcile_account(self, db: AsyncSession, integration: Integration, user: User, client: httpx.AsyncClient | None = None) -> int:
        secret = integration_service.read_secret(integration)

        if not secret:
            raise Unreadable(f"{integration.provider} has no api key on integration {integration.id}")

        if client is not None:
            return await self.against(db, integration, user, secret, client)

        async with httpx.AsyncClient(timeout=TIMEOUT) as opened:
            return await self.against(db, integration, user, secret, opened)

    async def refresh(self, db: AsyncSession, user: User) -> int:
        """What the app calls the moment a purchase goes through, so nothing waits for a webhook and nothing waits for a cron."""
        if not await self.claim_window(db, user):
            return 0

        statement = select(Integration).where(Integration.tenant_id == user.tenant_id, Integration.active.is_(True), Integration.provider.in_(self.answering()))
        touched = 0

        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            for integration in (await db.execute(statement)).scalars():
                try:
                    touched += await self.reconcile_account(db, integration, user, client)
                except Unreadable as missing:
                    logger.warning("[reconcile] %s", missing)

        return touched

    async def claim_window(self, db: AsyncSession, user: User) -> bool:
        """Takes the window to ask the gateway, and answers whether this caller got it: a device retrying and a screen coming back are otherwise one call each."""
        moment = now()
        statement = update(User).where(User.id == user.id, or_(User.reconciled_at.is_(None), User.reconciled_at < moment - COOLDOWN)).values(reconciled_at=moment)
        claimed = (await db.execute(statement)).rowcount == 1

        await db.commit()

        return claimed

    async def reconcile_stale(self, db: AsyncSession, limit: int = SWEEP_LIMIT) -> int:
        """The net under the other two, and it asks about nobody who looks fine: only a subscription whose period ran out in silence."""
        moment = now()
        overdue = and_(Subscription.status.in_(ELIGIBLE_SUBSCRIPTION_STATUSES), Subscription.access_until <= moment)

        # The clock closes what ran out and the provider is what says whether it renewed, so what just closed is still asked about.
        just_closed = and_(Subscription.status == SubscriptionStatus.EXPIRED, Subscription.expired_at > moment - RECENTLY_CLOSED)

        statement = select(Subscription.integration_id, Subscription.user_id).where(Subscription.integration_id.is_not(None), or_(overdue, just_closed)).group_by(Subscription.integration_id, Subscription.user_id).order_by(func.min(Subscription.access_until).asc()).limit(limit)
        accounts = list(await db.execute(statement))

        # The count alone bounds nothing, because how long a gateway takes to answer is its business and not ours.
        deadline = moment + SWEEP_WINDOW
        touched = 0
        unreadable = set()

        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            for position, (integration_id, user_id) in enumerate(accounts):
                # The oldest were asked about first, so whatever is left is what the next pass starts from.
                if now() >= deadline:
                    break

                if integration_id in unreadable:
                    continue

                integration = await db.get(Integration, integration_id)
                user = await db.get(User, user_id)

                if not integration.active or not PROVIDERS[integration.provider].queryable:
                    continue

                try:
                    touched += await self.reconcile_account(db, integration, user, client)
                except Unreadable as missing:
                    logger.warning("[reconcile] %s", missing)

                    # A key the gateway refuses refuses it for every account, and asking again is one more error row for the same fact.
                    unreadable.add(integration_id)

                    continue

                # The pace belongs between one call and the next, so a full pass spends its window on calls instead of ending on a pause nothing follows.
                if position < len(accounts) - 1:
                    await asyncio.sleep(PACE)

        return touched

    def answering(self) -> list:
        return [provider for provider, gateway in PROVIDERS.items() if gateway.queryable]

    async def against(self, db: AsyncSession, integration: Integration, user: User, secret: str, client: httpx.AsyncClient) -> int:
        provider = PROVIDERS[integration.provider]

        try:
            held = await provider.state_from_query(secret, user.token, client)
        except RateLimited as pause:
            logger.info("[reconcile] %s asked for %ss", integration.provider, pause.seconds)
            await asyncio.sleep(pause.seconds)

            return 0
        except httpx.HTTPStatusError as answer:
            if answer.response.status_code in REFUSED:
                await system_log_service.record(db, integration.tenant_id, user.id, LogLevel.ERROR, LogCategory.PURCHASE, f"{integration.provider} refused the api key of integration {integration.id}", {"integration_id": integration.id, "status": answer.response.status_code})
                await db.commit()

                raise Unreadable(f"{integration.provider} refused the api key of integration {integration.id}") from answer

            logger.warning("[reconcile] %s did not answer for %s: %s", integration.provider, user.token, answer)

            return 0
        except httpx.HTTPError as error:
            logger.warning("[reconcile] %s did not answer for %s: %s", integration.provider, user.token, error)

            return 0

        user.reconciled_at = now()

        return await self.apply(db, integration, user, held, complete=True)

    async def apply(self, db: AsyncSession, integration: Integration, user: User, held: list[ProviderPurchase], complete: bool) -> int:
        """The one place that decides what a subscription is, whichever of the two ways the state was obtained."""
        ours = await self.ours(db, integration, user)
        changes = 0

        for purchase in held:
            changes += await self.settle(db, integration, user, purchase, ours)

        # Only an answer that lists everything can say what is missing from it, and a notice is about the one purchase it names.
        if complete:
            for subscription in ours.values():
                if subscription.status in ELIGIBLE_SUBSCRIPTION_STATUSES:
                    changes += await self.close(db, subscription, SubscriptionStatus.EXPIRED, "the provider no longer holds it for this account")

        await db.commit()

        return changes

    async def ours(self, db: AsyncSession, integration: Integration, user: User) -> dict[str, Subscription]:
        """Both sides name a purchase by what the store sold, so the product is the handle."""
        statement = select(Subscription, ExternalProduct.external_id).join(ExternalProduct, ExternalProduct.id == Subscription.external_product_id).where(Subscription.integration_id == integration.id, Subscription.user_id == user.id)

        return {product: subscription for subscription, product in await db.execute(statement)}

    async def settle(self, db: AsyncSession, integration: Integration, user: User, purchase: ProviderPurchase, ours: dict[str, Subscription]) -> int:
        subscription = ours.pop(purchase.product_reference, None)

        if subscription is None:
            subscription = await self.same_purchase(db, integration, user, purchase)
            self.settled(ours, subscription)

        if subscription is None:
            return await self.open(db, integration, user, purchase)

        changed = await self.repoint(db, integration, subscription, purchase)
        changes = await self.align(db, subscription, purchase)

        if not changed:
            return changes

        await delivery_service.activate(db, subscription)

        return 1

    async def repoint(self, db: AsyncSession, integration: Integration, subscription: Subscription, purchase: ProviderPurchase) -> bool:
        """Buying a different product keeps the same purchase, so the row follows what was bought instead of a second one being opened."""
        product = await db.scalar(select(ExternalProduct).where(ExternalProduct.integration_id == integration.id, ExternalProduct.external_id == purchase.product_reference, ExternalProduct.active.is_(True)))

        if product is None or product.id == subscription.external_product_id:
            return False

        plan = await db.get(Plan, product.plan_id)

        subscription.external_product_id = product.id
        subscription.plan_id = product.plan_id

        # Somebody moving to another plan is starting over, and a plan says whether starting over owes a cycle.
        if plan.resume_delivery_policy == ResumeDeliveryPolicy.NEW_CYCLE:
            await delivery_service.release_cycle(db, subscription)

        return True

    def settled(self, ours: dict[str, Subscription], subscription: Subscription | None) -> None:
        """A purchase answered for is no longer a leftover, whichever product it had been listed under."""
        for product, row in list(ours.items()):
            if row is subscription:
                del ours[product]

    async def same_purchase(self, db: AsyncSession, integration: Integration, user: User, purchase: ProviderPurchase) -> Subscription | None:
        """The transaction inside this account, which is how an upgrade is recognised once the product changed."""
        if not purchase.external_id:
            return None

        return await db.scalar(select(Subscription).where(Subscription.integration_id == integration.id, Subscription.user_id == user.id, Subscription.external_id == purchase.external_id))

    def holder_statement(self, integration_id: int, purchase: ProviderPurchase):
        """A transaction is one row inside an integration, and this is that row wherever the store has since put it."""
        return select(Subscription).where(Subscription.integration_id == integration_id, Subscription.external_id == purchase.external_id)

    async def holder_of(self, db: AsyncSession, integration_id: int, purchase: ProviderPurchase) -> Subscription:
        return await db.scalar(self.holder_statement(integration_id, purchase))

    async def adopt(self, db: AsyncSession, subscription: Subscription, purchase: ProviderPurchase) -> None:
        """The store names the period it is selling by a transaction of its own, and a row still carrying the one before it is a row `same_purchase` and `holder_of` can no longer find."""
        if not purchase.external_id or purchase.external_id == subscription.external_id:
            return

        # Whoever already carries it is the row that purchase is, and this one is a leftover for the pass that closes them.
        if await self.holder_of(db, subscription.integration_id, purchase) is not None:
            return

        subscription.external_id = purchase.external_id

    async def hand_over(self, db: AsyncSession, subscription: Subscription, user: User, purchase: ProviderPurchase) -> int:
        """The receipt is now somebody else's, and the store only passes one on once nothing in it is active."""
        previous = subscription.user_id

        await delivery_service.end_benefits(db, subscription)

        subscription.user_id = user.id
        self.carry(subscription, purchase)

        await db.commit()

        await system_log_service.record(db, subscription.tenant_id, user.id, LogLevel.INFO, LogCategory.PURCHASE, "the store passed this receipt to another account", {"subscription_id": subscription.id, "from_user_id": previous, "to_user_id": user.id})

        # Whoever holds it now is a different person who just paid, and that is a cycle of their own.
        await delivery_service.release_cycle(db, subscription)
        await delivery_service.activate(db, subscription)

        return 1

    async def open(self, db: AsyncSession, integration: Integration, user: User, purchase: ProviderPurchase) -> int:
        if self.over(purchase):
            return 0

        product = await db.scalar(select(ExternalProduct).where(ExternalProduct.integration_id == integration.id, ExternalProduct.external_id == purchase.product_reference, ExternalProduct.active.is_(True)))

        if product is None or not purchase.external_id:
            await system_log_service.record(db, integration.tenant_id, user.id, LogLevel.WARNING, LogCategory.PURCHASE, f"{integration.provider} holds {purchase.product_reference} for an account here and nothing maps it", {"product": purchase.product_reference, "user_id": user.id})

            return 0

        subscription = Subscription(tenant_id=integration.tenant_id, user_id=user.id, plan_id=product.plan_id, integration_id=integration.id, external_product_id=product.id, external_id=purchase.external_id, status=SubscriptionStatus.PENDING, meta={})

        settled = await insert_or_read(db, subscription, self.holder_statement(integration.id, purchase))

        if settled is not subscription:
            return 0 if settled.user_id == user.id else await self.hand_over(db, settled, user, purchase)

        self.carry(subscription, purchase)
        await delivery_service.activate(db, subscription)

        return 1

    async def align(self, db: AsyncSession, subscription: Subscription, purchase: ProviderPurchase) -> int:
        if purchase.refunded_at is not None:
            return await self.close(db, subscription, SubscriptionStatus.REVOKED, "the provider refunded it")

        if self.over(purchase):
            return await self.close(db, subscription, SubscriptionStatus.EXPIRED, "the period the provider reports has ended")

        await self.adopt(db, subscription, purchase)

        before = self.snapshot(subscription)

        self.carry(subscription, purchase)

        if before == self.snapshot(subscription):
            return 0

        await delivery_service.activate(db, subscription)

        return 1

    def snapshot(self, subscription: Subscription) -> tuple:
        return (subscription.status, subscription.benefit_status, subscription.access_until, subscription.grace_until, subscription.cancel_at_period_end)

    def carry(self, subscription: Subscription, purchase: ProviderPurchase) -> None:
        """Every state a provider can report is written here, so nothing else in the codebase decides what a subscription is."""
        subscription.status = self.status_of(purchase)
        subscription.benefit_status = BenefitStatus.PAUSED if purchase.auto_resume_at else BenefitStatus.ACTIVE
        subscription.environment = purchase.environment
        subscription.started_at = purchase.first_purchased_at or subscription.started_at or purchase.purchased_at or now()
        subscription.current_period_started_at = purchase.purchased_at
        subscription.current_period_ends_at = purchase.period_ends_at
        subscription.access_until = purchase.grace_ends_at or purchase.period_ends_at
        subscription.grace_until = purchase.grace_ends_at
        subscription.trial_ends_at = purchase.period_ends_at if purchase.trial else None
        subscription.cancel_at_period_end = purchase.unsubscribed_at is not None
        subscription.canceled_at = purchase.unsubscribed_at
        subscription.expired_at = None
        subscription.meta = (subscription.meta or {}) | {"provider": {"store": purchase.store, "ownership": purchase.ownership, "period_type": purchase.period_type, "recurring": purchase.recurring}}

    def status_of(self, purchase: ProviderPurchase) -> SubscriptionStatus:
        """A gateway that names its own state is believed, and one that leaves it to the dates has it read off them."""
        if purchase.status is not None:
            return purchase.status

        if purchase.auto_resume_at:
            return SubscriptionStatus.SUSPENDED

        if purchase.grace_ends_at:
            return SubscriptionStatus.GRACE_PERIOD

        if purchase.trial:
            return SubscriptionStatus.TRIALING

        return SubscriptionStatus.ACTIVE

    async def close(self, db: AsyncSession, subscription: Subscription, status: SubscriptionStatus, reason: str) -> int:
        # Closing what is already closed is not a change, and rewriting `expired_at` would keep the account in the stale set forever.
        if subscription.status == status:
            return 0

        moment = now()

        subscription.status = status
        subscription.expired_at = moment
        subscription.access_until = moment
        subscription.benefit_status = BenefitStatus.ENDED

        await delivery_service.end_benefits(db, subscription)
        await system_log_service.record(db, subscription.tenant_id, subscription.user_id, LogLevel.WARNING, LogCategory.PURCHASE, f"subscription {subscription.id} was closed by a reconciliation: {reason}", {"subscription_id": subscription.id, "status": status})

        return 1

    def over(self, purchase: ProviderPurchase) -> bool:
        """A purchase that never renews has no deadline, so nothing about it can be past."""
        if purchase.status is not None:
            return purchase.status in CLOSED_SUBSCRIPTION_STATUSES

        deadline = purchase.grace_ends_at or purchase.period_ends_at

        return deadline is not None and deadline <= now()


reconciliation_service = ReconciliationService()
