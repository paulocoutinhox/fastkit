import logging
from datetime import timedelta

from sqlalchemy import and_, exists, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from enums.account import CreditTransactionType
from enums.subscription import ELIGIBLE_SUBSCRIPTION_STATUSES, SCHEDULE_ADVANCE_STATUSES, BenefitCadence, BenefitGrantStatus, BenefitPolicy, BenefitStatus, BenefitType, MissedCyclePolicy, SubscriptionStatus, UserEntitlementStatus
from enums.system_log import LogCategory, LogLevel
from helpers.dates import add_interval, now
from helpers.db import insert_or_read
from models.subscription import Benefit, BenefitGrant, Plan, PlanEntitlement, Subscription, SubscriptionBenefit, UserEntitlement
from models.user import User
from services.account import credit_transaction_service
from services.commerce import commerce_service
from services.subscription import benefit_policy_of
from services.system_log import system_log_service

# A delivery takes seconds, so a grant still processing after this belonged to a process that is gone.
ABANDONED_AFTER = timedelta(minutes=30)

# A grant that keeps failing stops being retried, or it would hold a slot of every pass forever.
MAX_ATTEMPTS = 5

# How many rows one pass reads at a time, bounded so a backlog is worked through across passes instead of in one.
DUE_BATCH = 100
EXPIRY_BATCH = 200
RETRY_BATCH = 50

logger = logging.getLogger(__name__)


class DeliveryService:
    """The engine that turns a live subscription into what the reader receives, one idempotent grant per cycle."""

    async def activate(self, db: AsyncSession, subscription: Subscription) -> list[BenefitGrant]:
        # A paused or pending subscription gives no access while it stays so, and its benefits wait with no date, so coming back walks to the cycle it lands in and pays none of the paused ones.
        if not subscription.is_eligible_for_benefits:
            await self.expire_entitlements(db, subscription)
            await db.execute(update(SubscriptionBenefit).where(SubscriptionBenefit.subscription_id == subscription.id, SubscriptionBenefit.status == BenefitStatus.ACTIVE).values(status=BenefitStatus.PAUSED, next_grant_at=None).execution_options(synchronize_session="fetch"))
            await db.commit()

            return []

        entitlements = await self.reconcile_entitlements(db, subscription)
        benefits = await self.snapshot_benefits(db, subscription, entitlements)

        grants = []

        for benefit in benefits:
            if benefit.grant_on_activation and benefit.last_grant_at is None:
                slot = self.first_due(benefit)
                grants.append(await self.run_cycle(db, benefit, self.activation_key(benefit, slot), slot))

        return grants

    def activation_key(self, benefit: SubscriptionBenefit, slot) -> str:
        """The first slot of a recurring benefit is also the one the due pass reads, so both doors name it alike and the grant key settles which one delivered it."""
        # A cycle opened again keeps a key of its own, because the slots of the one before are named by their dates and meeting them is what keeps the history from being paid twice.
        if benefit.cadence == BenefitCadence.RECURRING and benefit.cycle == 0:
            return self.cycle_key(slot)

        return f"activation:{benefit.cycle}"

    def landing(self, benefit: SubscriptionBenefit, since):
        """The cycle a recurring benefit is in now, walked from `since`, which is the one it owes after a stretch it was not running."""
        slot = since
        moment = now()

        while (following := add_interval(slot, benefit.interval_unit, benefit.interval_value)) <= moment:
            slot = following

        return slot

    def first_due(self, benefit: SubscriptionBenefit):
        """When a benefit new to the subscription is owed first: the cycle a recurring one is in now, the activation for one granted on it, and never for the rest."""
        if benefit.cadence == BenefitCadence.RECURRING:
            return self.landing(benefit, benefit.anchor_at)

        return benefit.anchor_at if benefit.grant_on_activation else None

    async def entitlements_of(self, db: AsyncSession, subscription: Subscription) -> dict[int, UserEntitlement]:
        result = await db.execute(select(UserEntitlement).where(UserEntitlement.subscription_id == subscription.id))

        return {row.entitlement_id: row for row in result.scalars()}

    async def benefits_of(self, db: AsyncSession, subscription: Subscription) -> dict[int, SubscriptionBenefit]:
        result = await db.execute(select(SubscriptionBenefit).where(SubscriptionBenefit.subscription_id == subscription.id))

        return {row.benefit_id: row for row in result.scalars()}

    async def reconcile_entitlements(self, db: AsyncSession, subscription: Subscription) -> dict[int, UserEntitlement]:
        result = await db.execute(select(PlanEntitlement).where(PlanEntitlement.plan_id == subscription.plan_id))
        plan_entitlements = list(result.scalars())

        by_entitlement = await self.entitlements_of(db, subscription)

        moment = now()
        promised = {}

        for plan_entitlement in plan_entitlements:
            row = by_entitlement.get(plan_entitlement.entitlement_id)

            if row is None:
                row = UserEntitlement(subscription_id=subscription.id, entitlement_id=plan_entitlement.entitlement_id, status=UserEntitlementStatus.ACTIVE, started_at=moment)
                row = await insert_or_read(db, row, select(UserEntitlement).where(UserEntitlement.subscription_id == subscription.id, UserEntitlement.entitlement_id == plan_entitlement.entitlement_id))
            else:
                row.status = UserEntitlementStatus.ACTIVE
                row.revoked_at = None

            row.expires_at = subscription.access_until
            promised[plan_entitlement.entitlement_id] = row

        # A subscription that moved to another plan holds what the plan it is on now promises, and not what the one before did.
        for entitlement_id, row in by_entitlement.items():
            if entitlement_id not in promised:
                row.status = UserEntitlementStatus.EXPIRED

        await db.commit()

        return promised

    async def snapshot_benefits(self, db: AsyncSession, subscription: Subscription, entitlements: dict[int, UserEntitlement]) -> list[SubscriptionBenefit]:
        catalog_benefits = []

        if entitlements:
            result = await db.execute(select(Benefit).where(Benefit.entitlement_id.in_(entitlements.keys()), Benefit.active.is_(True)))
            catalog_benefits = list(result.scalars())

        by_benefit = await self.benefits_of(db, subscription)

        anchor = subscription.started_at or now()
        promised = {}

        for benefit in catalog_benefits:
            if benefit.id in by_benefit:
                self.resume(by_benefit[benefit.id], anchor)
                promised[benefit.id] = by_benefit[benefit.id]

                continue

            snapshot = SubscriptionBenefit(
                subscription_id=subscription.id,
                benefit_id=benefit.id,
                user_entitlement_id=entitlements[benefit.entitlement_id].id,
                product_id=benefit.product_id,
                currency_id=benefit.currency_id,
                status=BenefitStatus.ACTIVE,
                benefit_type=benefit.type,
                target=benefit.target,
                quantity=benefit.quantity,
                cadence=benefit.cadence,
                interval_unit=benefit.interval_unit,
                interval_value=benefit.interval_value,
                grant_on_activation=benefit.grant_on_activation,
                missed_cycle_policy=benefit.missed_cycle_policy,
                anchor_at=anchor,
            )
            snapshot.next_grant_at = self.first_due(snapshot)

            snapshot = await insert_or_read(db, snapshot, select(SubscriptionBenefit).where(SubscriptionBenefit.subscription_id == subscription.id, SubscriptionBenefit.benefit_id == benefit.id))
            promised[benefit.id] = snapshot

        # The same rule as the entitlement above, and the one that stops an upgrade from paying the promise of both plans.
        for benefit_id, snapshot in by_benefit.items():
            if benefit_id not in promised:
                snapshot.status = BenefitStatus.ENDED
                snapshot.next_grant_at = None

        await db.commit()

        return list(promised.values())

    def live_subscription(self):
        """Answers the condition a subscription still delivering meets, which a suspended one never does and would otherwise hold a slot of every pass forever."""
        return and_(Subscription.status.in_(ELIGIBLE_SUBSCRIPTION_STATUSES), Subscription.benefit_status == BenefitStatus.ACTIVE)

    async def process_due(self, db: AsyncSession) -> list[BenefitGrant]:
        moment = now()

        # A slot whose grant waits on the retry pass belongs to that pass, and reading it here again only filled the batch every other benefit waits behind.
        waiting = exists().where(BenefitGrant.subscription_benefit_id == SubscriptionBenefit.id, BenefitGrant.status.in_((BenefitGrantStatus.FAILED, BenefitGrantStatus.PROCESSING)))

        statement = (
            select(SubscriptionBenefit)
            .options(selectinload(SubscriptionBenefit.subscription))
            .join(Subscription, Subscription.id == SubscriptionBenefit.subscription_id)
            .where(SubscriptionBenefit.status == BenefitStatus.ACTIVE, SubscriptionBenefit.cadence == BenefitCadence.RECURRING, SubscriptionBenefit.next_grant_at.is_not(None), SubscriptionBenefit.next_grant_at <= moment, self.live_subscription(), ~waiting)
            .order_by(SubscriptionBenefit.next_grant_at.asc())
            .limit(DUE_BATCH)
        )
        result = await db.execute(statement)

        grants = []

        for benefit in result.scalars().unique():
            scheduled_at = self.resolve_due_slot(benefit, moment)

            if scheduled_at is None:
                await db.commit()

                continue

            grants.append(await self.run_cycle(db, benefit, self.cycle_key(scheduled_at), scheduled_at))

        return grants

    def resolve_due_slot(self, benefit: SubscriptionBenefit, moment):
        """Which slot a benefit behind on its cycles delivers now, and what becomes of the ones it missed."""
        latest = benefit.next_grant_at
        following = add_interval(latest, benefit.interval_unit, benefit.interval_value)

        if following > moment:
            return latest

        while following <= moment:
            latest = following
            following = add_interval(latest, benefit.interval_unit, benefit.interval_value)

        if benefit.missed_cycle_policy == MissedCyclePolicy.CATCH_UP:
            return benefit.next_grant_at

        if benefit.missed_cycle_policy == MissedCyclePolicy.LATEST_ONLY:
            return latest

        # Under `skip`, what the downtime missed is not made up for, and the schedule resumes ahead of now.
        benefit.next_grant_at = following

        return None

    def cycle_key(self, moment) -> str:
        return f"{moment:%Y%m%d%H%M%S}"

    async def already_held_by_user(self, db: AsyncSession, benefit: SubscriptionBenefit) -> bool:
        """A benefit granted once per person stays granted across the subscriptions that come and go."""
        subscription = await db.get(Subscription, benefit.subscription_id)

        twins = select(SubscriptionBenefit.id).join(Subscription, Subscription.id == SubscriptionBenefit.subscription_id).where(Subscription.user_id == subscription.user_id, SubscriptionBenefit.benefit_id == benefit.benefit_id, SubscriptionBenefit.id != benefit.id)
        statement = select(BenefitGrant.id).where(BenefitGrant.subscription_benefit_id.in_(twins), BenefitGrant.status == BenefitGrantStatus.COMPLETED)

        return await db.scalar(statement) is not None

    async def policy_allows(self, db: AsyncSession, benefit: SubscriptionBenefit) -> bool:
        """A trial opens the catalog without handing out what outlives it, and the plan says how far that goes."""
        subscription = await db.get(Subscription, benefit.subscription_id)
        policy = benefit_policy_of(subscription, await db.get(Plan, subscription.plan_id))

        if policy == BenefitPolicy.ALL:
            return True

        if policy == BenefitPolicy.NONE:
            return False

        return benefit.benefit_type == BenefitType.ACCESS

    async def skip(self, db: AsyncSession, benefit: SubscriptionBenefit, grant: BenefitGrant, grant_key: str, reason: str) -> BenefitGrant:
        """A cycle nothing was handed out in is still a cycle, so it is recorded and the schedule moves past it."""
        grant.status = BenefitGrantStatus.SKIPPED
        grant.error_code = reason
        grant.completed_at = now()
        self.advance(benefit, grant)

        return await self.settled(db, grant, grant_key)

    async def run_cycle(self, db: AsyncSession, benefit: SubscriptionBenefit, cycle_key: str, scheduled_at) -> BenefitGrant:
        grant_key = f"{benefit.id}:{cycle_key}"

        existing = await db.scalar(select(BenefitGrant).where(BenefitGrant.grant_key == grant_key))

        if existing is not None:
            # A cycle already closed never holds the schedule on itself, or the benefit meets its own grant on every pass and stops delivering for good.
            self.advance(benefit, existing)
            await db.commit()

            return existing

        grant = BenefitGrant(subscription_benefit_id=benefit.id, grant_key=grant_key, cycle_key=cycle_key, scheduled_at=scheduled_at, status=BenefitGrantStatus.PROCESSING, requested_quantity=benefit.quantity, attempts=1, started_at=now())

        if benefit.cadence == BenefitCadence.ONCE_PER_USER and await self.already_held_by_user(db, benefit):
            return await self.skip(db, benefit, grant, grant_key, "already_held_by_user")

        if not await self.policy_allows(db, benefit):
            return await self.skip(db, benefit, grant, grant_key, "withheld_by_plan_policy")

        written = await self.settled(db, grant, grant_key)

        if written is not grant:
            return written

        await self.deliver(db, benefit, grant)
        self.advance(benefit, grant)

        await db.commit()

        return grant

    async def settled(self, db: AsyncSession, grant: BenefitGrant, grant_key: str) -> BenefitGrant:
        """The row of this cycle, whoever wrote it: two nodes can pass the read at once, and the grant key is what settles which one did."""
        written = await insert_or_read(db, grant, select(BenefitGrant).where(BenefitGrant.grant_key == grant_key))
        await db.commit()

        return written

    def resume(self, benefit: SubscriptionBenefit, anchor) -> None:
        """A subscription can end and come back, and a benefit left ended would take the entitlement back and never deliver again."""
        if benefit.status == BenefitStatus.ACTIVE:
            return

        benefit.status = BenefitStatus.ACTIVE

        if benefit.cadence != BenefitCadence.RECURRING:
            return

        # A lapse is not a cycle the engine missed, so coming back owes the slot it lands in and none of the ones before it.
        # A date found on a benefit that was not running is one a pass wrote after loading it, and never one worth resuming from.
        benefit.next_grant_at = self.landing(benefit, add_interval(benefit.last_grant_at, benefit.interval_unit, benefit.interval_value) if benefit.last_grant_at else anchor)

    def advance(self, benefit: SubscriptionBenefit, grant: BenefitGrant) -> None:
        """A cycle that ran is a cycle that happened, however little it handed over, and only a failure holds the schedule for the retry sweep."""
        if grant.status not in SCHEDULE_ADVANCE_STATUSES:
            return

        benefit.last_grant_at = now()

        if benefit.cadence != BenefitCadence.RECURRING:
            benefit.next_grant_at = None

            return

        benefit.next_grant_at = add_interval(grant.scheduled_at, benefit.interval_unit, benefit.interval_value)

    async def deliver(self, db: AsyncSession, benefit: SubscriptionBenefit, grant: BenefitGrant) -> None:
        handlers = {BenefitType.ACCESS: self.deliver_access, BenefitType.CREDIT: self.deliver_credit, BenefitType.PRODUCT: self.deliver_product}

        try:
            await handlers[benefit.benefit_type](db, benefit, grant)
        except Exception as error:
            logger.exception("[delivery] grant %s failed", grant.grant_key)

            grant.status = BenefitGrantStatus.FAILED
            grant.error_code = type(error).__name__
            grant.error_message = str(error)

        grant.completed_at = now()

    async def deliver_access(self, db: AsyncSession, benefit: SubscriptionBenefit, grant: BenefitGrant) -> None:
        entitlement = await db.get(UserEntitlement, benefit.user_entitlement_id)
        entitlement.status = UserEntitlementStatus.ACTIVE
        entitlement.revoked_at = None

        grant.status = BenefitGrantStatus.COMPLETED
        grant.granted_quantity = 1
        grant.result = {"entitlement_id": entitlement.entitlement_id}

    async def deliver_credit(self, db: AsyncSession, benefit: SubscriptionBenefit, grant: BenefitGrant) -> None:
        subscription = await db.get(Subscription, benefit.subscription_id)
        plan = await db.get(Plan, subscription.plan_id)

        # The statement says what put the credits there, and the currency is already a column of its own.
        transaction = await credit_transaction_service.move(db, subscription.user_id, benefit.currency_id, CreditTransactionType.CREDIT, benefit.quantity, plan.name, grant.grant_key, grant.id, {})

        grant.status = BenefitGrantStatus.COMPLETED
        grant.granted_quantity = benefit.quantity
        grant.result = {"credit_transaction_id": transaction.id, "balance_after": transaction.balance_after}

    async def release_cycle(self, db: AsyncSession, subscription: Subscription) -> int:
        """Opens a fresh cycle for somebody who is starting over instead of coming back, so the next grant key is one nobody used."""
        cycles = update(SubscriptionBenefit).where(SubscriptionBenefit.subscription_id == subscription.id).values(cycle=SubscriptionBenefit.cycle + 1, last_grant_at=None).execution_options(synchronize_session="fetch")
        released = (await db.execute(cycles)).rowcount

        await db.commit()

        return released

    async def open_new_cycle(self, db: AsyncSession, subscription: Subscription, operator: User) -> list[BenefitGrant]:
        """The one way to force what coming back does not give, so who asked for it is part of the record."""
        released = await self.release_cycle(db, subscription)

        await system_log_service.record(db, subscription.tenant_id, subscription.user_id, LogLevel.INFO, LogCategory.PURCHASE, "new cycle opened by an operator", {"subscription_id": subscription.id, "operator_id": operator.id, "released": released})

        return await self.activate(db, subscription)

    async def deliver_product(self, db: AsyncSession, benefit: SubscriptionBenefit, grant: BenefitGrant) -> None:
        """What a plan hands over is the account's from then on, so a later cycle meets it already held instead of writing a second row."""
        subscription = await db.get(Subscription, benefit.subscription_id)
        held, granted = await commerce_service.grant(db, subscription.user_id, benefit.product_id, grant.grant_key, subscription_id=subscription.id, benefit_grant_id=grant.id)

        grant.result = {"product_id": benefit.product_id, "user_product_id": held.id}

        if not granted:
            grant.status = BenefitGrantStatus.SKIPPED
            grant.error_code = "already_held_by_user"

            return

        grant.status = BenefitGrantStatus.COMPLETED
        grant.granted_quantity = 1

    async def expire_subscriptions(self, db: AsyncSession) -> list[Subscription]:
        moment = now()

        statement = select(Subscription).where(Subscription.status.in_(ELIGIBLE_SUBSCRIPTION_STATUSES), Subscription.access_until.is_not(None), Subscription.access_until < moment).limit(EXPIRY_BATCH)
        result = await db.execute(statement)
        expired = list(result.scalars())

        closed = []

        for subscription in expired:
            # A renewal lands between the read and this write, so the row is closed only while it is still past its period.
            # The benefits end with it, so a row still answering `active` here would say the opposite of every one of them.
            still = update(Subscription).where(Subscription.id == subscription.id, Subscription.status.in_(ELIGIBLE_SUBSCRIPTION_STATUSES), Subscription.access_until < moment).values(status=SubscriptionStatus.EXPIRED, expired_at=moment, benefit_status=BenefitStatus.ENDED)

            if (await db.execute(still)).rowcount != 1:
                continue

            await db.refresh(subscription)
            await self.end_benefits(db, subscription)
            closed.append(subscription)

        await db.commit()

        return closed

    async def end_benefits(self, db: AsyncSession, subscription: Subscription) -> None:
        result = await db.execute(select(SubscriptionBenefit).where(SubscriptionBenefit.subscription_id == subscription.id))

        for benefit in result.scalars():
            benefit.status = BenefitStatus.ENDED
            benefit.next_grant_at = None

        await self.expire_entitlements(db, subscription)

    async def expire_entitlements(self, db: AsyncSession, subscription: Subscription) -> None:
        entitlements = await db.execute(select(UserEntitlement).where(UserEntitlement.subscription_id == subscription.id))

        for entitlement in entitlements.scalars():
            entitlement.status = UserEntitlementStatus.EXPIRED

    def takeable(self):
        """What this pass is allowed to pick up, written once so the read and the claim can never come to mean different things."""
        abandoned = and_(BenefitGrant.status == BenefitGrantStatus.PROCESSING, BenefitGrant.started_at < now() - ABANDONED_AFTER)

        return and_(or_(BenefitGrant.status == BenefitGrantStatus.FAILED, abandoned), BenefitGrant.attempts < MAX_ATTEMPTS)

    def exhausted(self):
        """A grant whose last attempt died with the node running it: no pass may take it again, and only closing it lets its benefit move on."""
        return and_(BenefitGrant.status == BenefitGrantStatus.PROCESSING, BenefitGrant.started_at < now() - ABANDONED_AFTER, BenefitGrant.attempts >= MAX_ATTEMPTS)

    async def claim(self, db: AsyncSession, grant_id: int) -> bool:
        """Takes a grant for this pass, and answers whether it was the one that got it: a pass running past its interval overlaps the next, and so does `run-delivery` beside it."""
        statement = update(BenefitGrant).where(BenefitGrant.id == grant_id, self.takeable()).values(status=BenefitGrantStatus.PROCESSING, attempts=BenefitGrant.attempts + 1, error_code=None, error_message=None, started_at=now())
        claimed = (await db.execute(statement)).rowcount == 1

        await db.commit()

        return claimed

    async def retry_failed_grants(self, db: AsyncSession) -> list[BenefitGrant]:
        """A grant still processing long after it started was abandoned by a node that died mid-flight, and the key that stops a double delivery would otherwise stop it being delivered at all."""
        statement = select(BenefitGrant).options(selectinload(BenefitGrant.subscription_benefit)).where(or_(self.takeable(), self.exhausted())).order_by(BenefitGrant.id.asc()).limit(RETRY_BATCH)
        result = await db.execute(statement)
        worked = []

        for grant in result.scalars().unique():
            # What the subscription owed when the cycle ran it may not owe now, and a retry must not hand over a cycle that ended in between.
            if not await self.still_owed(db, grant.subscription_benefit):
                self.drop(grant, "subscription_no_longer_eligible")
                worked.append(grant)

                continue

            if grant.attempts >= MAX_ATTEMPTS:
                if await self.close_exhausted(db, grant.id):
                    worked.append(grant)

                continue

            # The read said it was takeable and the claim is what takes it, so an overlapping pass that got there first leaves this one nothing to do.
            if not await self.claim(db, grant.id):
                continue

            # The claim commits, and a commit expires every object the session holds, so the row is read again with the benefit it is delivered against.
            grant = await db.scalar(select(BenefitGrant).options(selectinload(BenefitGrant.subscription_benefit)).where(BenefitGrant.id == grant.id))

            await self.deliver(db, grant.subscription_benefit, grant)

            if grant.status == BenefitGrantStatus.FAILED and grant.attempts >= MAX_ATTEMPTS:
                await self.give_up(db, grant)

            self.advance(grant.subscription_benefit, grant)
            worked.append(grant)

        await db.commit()

        return worked

    async def close_exhausted(self, db: AsyncSession, grant_id: int) -> bool:
        """Closes a grant whose last attempt was cut short, taken the way a claim takes one so two passes never close it twice."""
        statement = update(BenefitGrant).where(BenefitGrant.id == grant_id, self.exhausted()).values(status=BenefitGrantStatus.FAILED, error_code="abandoned", error_message="the last attempt never finished")

        if (await db.execute(statement)).rowcount != 1:
            await db.commit()

            return False

        grant = await db.scalar(select(BenefitGrant).options(selectinload(BenefitGrant.subscription_benefit)).where(BenefitGrant.id == grant_id))

        await self.give_up(db, grant)
        self.advance(grant.subscription_benefit, grant)
        await db.commit()

        return True

    async def give_up(self, db: AsyncSession, grant: BenefitGrant) -> None:
        """The attempts ran out, so the cycle closes instead of being held: a failure nobody will pick up again would stop this benefit for good and say so nowhere."""
        subscription = await db.get(Subscription, grant.subscription_benefit.subscription_id)
        failure = grant.error_code

        grant.status = BenefitGrantStatus.SKIPPED
        grant.error_code = "given_up_after_max_attempts"
        grant.completed_at = now()

        description = f"the delivery of {grant.grant_key} was given up on after {grant.attempts} attempts"

        await system_log_service.record(db, subscription.tenant_id, subscription.user_id, LogLevel.ERROR, LogCategory.PURCHASE, description, {"subscription_id": subscription.id, "benefit_grant_id": grant.id, "error_code": failure, "error": grant.error_message})

    async def still_owed(self, db: AsyncSession, benefit: SubscriptionBenefit) -> bool:
        if benefit.status != BenefitStatus.ACTIVE:
            return False

        return (await db.get(Subscription, benefit.subscription_id)).is_eligible_for_benefits

    def drop(self, grant: BenefitGrant, reason: str) -> None:
        """A cycle nobody owes anymore is closed where it stands, so the sweep stops picking it up on every pass."""
        grant.status = BenefitGrantStatus.SKIPPED
        grant.error_code = reason
        grant.error_message = None
        grant.completed_at = now()


delivery_service = DeliveryService()
