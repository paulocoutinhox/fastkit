from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy import select

from enums.subscription import BenefitCadence, BenefitGrantStatus, BenefitPolicy, BenefitStatus, BenefitType, IntervalUnit, MissedCyclePolicy, SubscriptionStatus, UserEntitlementStatus
from helpers.dates import now
from models.account import CreditTransaction
from models.commerce import UserProduct
from models.subscription import BenefitGrant, SubscriptionBenefit, UserEntitlement
from services.delivery import delivery_service
from tests.factories import make_benefit, make_currency, make_entitlement, make_plan, make_plan_entitlement, make_product, make_subscription


@pytest_asyncio.fixture
async def subscribed(db, tenant, member):
    plan = await make_plan(db, tenant)
    entitlement = await make_entitlement(db, tenant)

    await make_plan_entitlement(db, plan, entitlement)

    subscription = await make_subscription(db, tenant, member, plan)

    return {"plan": plan, "entitlement": entitlement, "subscription": subscription}


async def balance_of(db, user, currency) -> int:
    """What the account holds of one currency, read from the balance the ledger of that currency explains."""
    from services.account import user_balance_service

    held = await user_balance_service.list_for_user(db, user.id)

    return next((row.amount for row in held if row.currency_id == currency.id), 0)


async def test_activation_reconciles_the_entitlements(db, subscribed):
    await delivery_service.activate(db, subscribed["subscription"])

    rows = (await db.execute(select(UserEntitlement))).scalars().all()

    assert len(rows) == 1
    assert rows[0].status == UserEntitlementStatus.ACTIVE


async def test_activation_snapshots_the_benefits(db, subscribed):
    await make_benefit(db, subscribed["entitlement"], quantity=3)

    await delivery_service.activate(db, subscribed["subscription"])

    rows = (await db.execute(select(SubscriptionBenefit))).scalars().all()

    assert len(rows) == 1
    assert rows[0].quantity == 3
    assert rows[0].target == "member"


async def test_the_snapshot_survives_a_later_edit_of_the_benefit_it_was_taken_from(db, subscribed):
    benefit = await make_benefit(db, subscribed["entitlement"], quantity=3)

    await delivery_service.activate(db, subscribed["subscription"])

    benefit.quantity = 99
    await db.commit()

    await delivery_service.activate(db, subscribed["subscription"])

    rows = (await db.execute(select(SubscriptionBenefit))).scalars().all()

    assert rows[0].quantity == 3


async def test_activation_delivers_an_access_benefit(db, subscribed):
    await make_benefit(db, subscribed["entitlement"])

    grants = await delivery_service.activate(db, subscribed["subscription"])

    assert len(grants) == 1
    assert grants[0].status == BenefitGrantStatus.COMPLETED
    assert grants[0].granted_quantity == 1


async def test_activation_delivers_a_credit_benefit(db, subscribed, member, currency):
    await make_benefit(db, subscribed["entitlement"], type=BenefitType.CREDIT, currency_id=currency.id, target="gold", quantity=50)

    grants = await delivery_service.activate(db, subscribed["subscription"])

    await db.refresh(member)

    assert grants[0].status == BenefitGrantStatus.COMPLETED
    assert await balance_of(db, member, currency) == 50


async def test_activation_delivers_a_product_benefit(db, subscribed, member, tenant):
    product = await make_product(db, tenant)

    await make_benefit(db, subscribed["entitlement"], type=BenefitType.PRODUCT, target="handbook", quantity=1, product_id=product.id)

    grants = await delivery_service.activate(db, subscribed["subscription"])
    owned = (await db.execute(select(UserProduct))).scalars().all()

    assert grants[0].status == BenefitGrantStatus.COMPLETED
    assert [row.product_id for row in owned] == [product.id]


async def test_a_product_the_account_already_owns_is_skipped(db, subscribed, member, tenant):
    product = await make_product(db, tenant)

    db.add(UserProduct(user_id=member.id, product_id=product.id))
    await db.commit()

    await make_benefit(db, subscribed["entitlement"], type=BenefitType.PRODUCT, target="handbook", quantity=1, product_id=product.id)

    grants = await delivery_service.activate(db, subscribed["subscription"])

    assert grants[0].status == BenefitGrantStatus.SKIPPED
    assert grants[0].error_code == "already_held_by_user"


async def test_activation_is_idempotent(db, subscribed, member, currency):
    await make_benefit(db, subscribed["entitlement"], type=BenefitType.CREDIT, currency_id=currency.id, target="gold", quantity=50)

    await delivery_service.activate(db, subscribed["subscription"])
    await delivery_service.activate(db, subscribed["subscription"])

    await db.refresh(member)
    grants = (await db.execute(select(BenefitGrant))).scalars().all()

    assert len(grants) == 1
    assert await balance_of(db, member, currency) == 50


async def test_a_subscription_that_is_not_eligible_delivers_nothing(db, subscribed):
    await make_benefit(db, subscribed["entitlement"])

    subscribed["subscription"].status = SubscriptionStatus.EXPIRED
    await db.commit()

    assert await delivery_service.activate(db, subscribed["subscription"]) == []


async def test_a_benefit_that_does_not_grant_on_activation_only_gets_scheduled(db, subscribed):
    await make_benefit(db, subscribed["entitlement"], cadence=BenefitCadence.RECURRING, interval_unit=IntervalUnit.MONTH, interval_value=1, grant_on_activation=False)

    grants = await delivery_service.activate(db, subscribed["subscription"])

    assert grants == []

    snapshot = (await db.execute(select(SubscriptionBenefit))).scalars().one()

    assert snapshot.next_grant_at is not None


async def test_a_due_recurring_cycle_is_delivered_and_rescheduled(db, subscribed, member, currency):
    await make_benefit(db, subscribed["entitlement"], type=BenefitType.CREDIT, currency_id=currency.id, target="gold", quantity=10, cadence=BenefitCadence.RECURRING, interval_unit=IntervalUnit.MONTH, interval_value=1, grant_on_activation=False)

    await delivery_service.activate(db, subscribed["subscription"])

    snapshot = (await db.execute(select(SubscriptionBenefit))).scalars().one()
    snapshot.next_grant_at = now() - timedelta(minutes=1)
    await db.commit()

    grants = await delivery_service.process_due(db)

    await db.refresh(snapshot)
    await db.refresh(member)

    assert len(grants) == 1
    assert await balance_of(db, member, currency) == 10
    assert snapshot.next_grant_at > now()


async def test_a_cycle_that_is_not_due_yet_is_left_alone(db, subscribed, currency):
    await make_benefit(db, subscribed["entitlement"], type=BenefitType.CREDIT, currency_id=currency.id, target="gold", quantity=10, cadence=BenefitCadence.RECURRING, interval_unit=IntervalUnit.MONTH, interval_value=1, grant_on_activation=False)

    await delivery_service.activate(db, subscribed["subscription"])

    snapshot = (await db.execute(select(SubscriptionBenefit))).scalars().one()
    snapshot.next_grant_at = now() + timedelta(days=1)
    await db.commit()

    assert await delivery_service.process_due(db) == []


async def test_a_cycle_of_a_subscription_that_stopped_being_eligible_is_left_alone(db, subscribed, currency):
    await make_benefit(db, subscribed["entitlement"], type=BenefitType.CREDIT, currency_id=currency.id, target="gold", quantity=10, cadence=BenefitCadence.RECURRING, interval_unit=IntervalUnit.MONTH, interval_value=1, grant_on_activation=False)

    await delivery_service.activate(db, subscribed["subscription"])

    snapshot = (await db.execute(select(SubscriptionBenefit))).scalars().one()
    snapshot.next_grant_at = now() - timedelta(minutes=1)
    subscribed["subscription"].status = SubscriptionStatus.SUSPENDED
    await db.commit()

    assert await delivery_service.process_due(db) == []


async def test_expiring_a_subscription_ends_its_benefits(db, subscribed):
    await make_benefit(db, subscribed["entitlement"])

    await delivery_service.activate(db, subscribed["subscription"])

    subscribed["subscription"].access_until = now() - timedelta(days=1)
    await db.commit()

    expired = await delivery_service.expire_subscriptions(db)

    snapshot = (await db.execute(select(SubscriptionBenefit))).scalars().one()
    entitlement = (await db.execute(select(UserEntitlement))).scalars().one()

    assert len(expired) == 1
    assert expired[0].status == SubscriptionStatus.EXPIRED
    assert snapshot.status == BenefitStatus.ENDED
    assert snapshot.next_grant_at is None
    assert entitlement.status == UserEntitlementStatus.EXPIRED


async def test_a_subscription_still_inside_its_window_is_not_expired(db, subscribed):
    subscribed["subscription"].access_until = now() + timedelta(days=1)
    await db.commit()

    assert await delivery_service.expire_subscriptions(db) == []


async def test_a_failed_grant_is_recorded_and_retried(db, subscribed, member, monkeypatch, currency):
    await make_benefit(db, subscribed["entitlement"], type=BenefitType.CREDIT, currency_id=currency.id, target="gold", quantity=10)

    async def broken(*args, **kwargs):
        raise RuntimeError("provider down")

    monkeypatch.setattr(delivery_service, "deliver_credit", broken)

    grants = await delivery_service.activate(db, subscribed["subscription"])

    assert grants[0].status == BenefitGrantStatus.FAILED
    assert grants[0].error_code == "RuntimeError"
    assert grants[0].error_message == "provider down"

    monkeypatch.undo()

    retried = await delivery_service.retry_failed_grants(db)

    await db.refresh(member)

    assert len(retried) == 1
    assert retried[0].status == BenefitGrantStatus.COMPLETED
    assert retried[0].attempts == 2
    assert await balance_of(db, member, currency) == 10


async def build_recurring(currency, db, subscribed, **overrides):
    """A monthly credit benefit whose schedule the test then moves into the past."""
    await make_benefit(db, subscribed["entitlement"], type=BenefitType.CREDIT, currency_id=currency.id, target="gold", quantity=1, cadence=BenefitCadence.RECURRING, interval_unit=IntervalUnit.MONTH, interval_value=1, grant_on_activation=False, **overrides)

    await delivery_service.activate(db, subscribed["subscription"])

    return (await db.execute(select(SubscriptionBenefit))).scalars().one()


async def run_from(db, snapshot, scheduled: str):
    snapshot.next_grant_at = datetime.fromisoformat(scheduled).replace(tzinfo=timezone.utc)
    await db.commit()

    grants = await delivery_service.process_due(db)
    await db.refresh(snapshot)

    return grants


@pytest.mark.parametrize("scheduled,expected", [("2026-01-31T00:00:00", "2026-02-28T00:00:00"), ("2026-03-15T00:00:00", "2026-04-15T00:00:00")])
async def test_catching_up_walks_one_interval_a_pass(db, subscribed, scheduled, expected, currency):
    """The month arithmetic is what decides the next slot, and a short month never overshoots."""
    snapshot = await build_recurring(currency, db, subscribed, missed_cycle_policy=MissedCyclePolicy.CATCH_UP)

    await run_from(db, snapshot, scheduled)

    assert snapshot.next_grant_at == datetime.fromisoformat(expected).replace(tzinfo=timezone.utc)


async def test_catching_up_delivers_the_oldest_missed_cycle_first(db, subscribed, member, currency):
    snapshot = await build_recurring(currency, db, subscribed, missed_cycle_policy=MissedCyclePolicy.CATCH_UP)

    grants = await run_from(db, snapshot, "2026-01-15T00:00:00")

    assert grants[0].scheduled_at == datetime(2026, 1, 15, tzinfo=timezone.utc)

    await db.refresh(member)

    assert await balance_of(db, member, currency) == 1


async def test_only_the_latest_missed_cycle_is_delivered(db, subscribed, member, currency):
    snapshot = await build_recurring(currency, db, subscribed, missed_cycle_policy=MissedCyclePolicy.LATEST_ONLY)

    grants = await run_from(db, snapshot, "2026-01-15T00:00:00")

    assert grants[0].scheduled_at > datetime(2026, 5, 15, tzinfo=timezone.utc)
    assert snapshot.next_grant_at > now()

    await db.refresh(member)

    assert await balance_of(db, member, currency) == 1, "the months it was down are not paid out one by one"


async def test_skipping_pays_nothing_for_the_months_it_was_down(db, subscribed, member, currency):
    snapshot = await build_recurring(currency, db, subscribed, missed_cycle_policy=MissedCyclePolicy.SKIP)

    grants = await run_from(db, snapshot, "2026-01-15T00:00:00")

    assert grants == []
    assert snapshot.next_grant_at > now()

    await db.refresh(member)

    assert await balance_of(db, member, currency) == 0


async def test_a_cycle_that_is_merely_due_is_delivered_whatever_the_policy(db, subscribed, member, currency):
    """The cron runs every five minutes, so a slot a few minutes old is the normal case and never a missed one."""
    snapshot = await build_recurring(currency, db, subscribed, missed_cycle_policy=MissedCyclePolicy.SKIP)

    grants = await run_from(db, snapshot, (now() - timedelta(minutes=5)).replace(tzinfo=None).isoformat())

    assert len(grants) == 1

    await db.refresh(member)

    assert await balance_of(db, member, currency) == 1


async def test_a_plan_without_entitlements_snapshots_nothing(db, tenant, member):
    plan = await make_plan(db, tenant)
    subscription = await make_subscription(db, tenant, member, plan)

    assert await delivery_service.activate(db, subscription) == []


async def test_a_benefit_granted_once_per_user_is_not_granted_again_by_a_new_subscription(db, subscribed, tenant, member, currency):
    """The person is the same one, and a subscription that comes and goes does not make them new."""
    await make_benefit(db, subscribed["entitlement"], type=BenefitType.CREDIT, currency_id=currency.id, target="gold", quantity=5, cadence=BenefitCadence.ONCE_PER_USER, grant_on_activation=True)

    await delivery_service.activate(db, subscribed["subscription"])
    await db.refresh(member)

    assert await balance_of(db, member, currency) == 5

    again = await make_subscription(db, tenant, member, subscribed["plan"])
    grants = await delivery_service.activate(db, again)

    await db.refresh(member)

    assert [grant.status for grant in grants] == [BenefitGrantStatus.SKIPPED]
    assert grants[0].error_code == "already_held_by_user"
    assert await balance_of(db, member, currency) == 5, "the second subscription pays nothing a second time"


async def test_a_recurring_benefit_is_granted_again_by_a_new_subscription(db, subscribed, tenant, member, currency):
    await make_benefit(db, subscribed["entitlement"], type=BenefitType.CREDIT, currency_id=currency.id, target="gold", quantity=5, cadence=BenefitCadence.RECURRING, interval_unit=IntervalUnit.MONTH, interval_value=1, grant_on_activation=True)

    await delivery_service.activate(db, subscribed["subscription"])
    await delivery_service.activate(db, await make_subscription(db, tenant, member, subscribed["plan"]))

    await db.refresh(member)

    assert await balance_of(db, member, currency) == 10


async def expired_holding(db, subscribed, tenant, member, **benefit):
    product = await make_product(db, tenant)

    await make_benefit(db, subscribed["entitlement"], type=BenefitType.PRODUCT, target="handbook", quantity=1, grant_on_activation=True, product_id=product.id, **benefit)

    await delivery_service.activate(db, subscribed["subscription"])

    subscribed["subscription"].access_until = now() - timedelta(days=1)
    await db.commit()

    await delivery_service.expire_subscriptions(db)

    return (await db.execute(select(UserProduct).where(UserProduct.user_id == member.id))).scalars().one()


async def test_a_product_the_account_holds_stays_its_own_when_the_subscription_ends(db, subscribed, tenant, member):
    """What entered is the account's for good, so nothing a subscription stops paying for takes it back."""
    owned = await expired_holding(db, subscribed, tenant, member, cadence=BenefitCadence.ON_ACTIVATION)
    grant = await db.get(BenefitGrant, owned.benefit_grant_id)

    assert owned.product_id
    assert grant.status == BenefitGrantStatus.COMPLETED


async def test_a_product_a_recurring_benefit_delivered_stays_its_own_too(db, subscribed, tenant, member):
    owned = await expired_holding(db, subscribed, tenant, member, cadence=BenefitCadence.RECURRING, interval_unit=IntervalUnit.MONTH, interval_value=1)

    assert owned.product_id


async def test_a_credit_the_subscription_granted_stays_in_the_wallet(db, subscribed, tenant, member, currency):
    await make_benefit(db, subscribed["entitlement"], type=BenefitType.CREDIT, currency_id=currency.id, target="gold", quantity=7, cadence=BenefitCadence.ON_ACTIVATION, grant_on_activation=True)

    await delivery_service.activate(db, subscribed["subscription"])

    subscribed["subscription"].access_until = now() - timedelta(days=1)
    await db.commit()

    await delivery_service.expire_subscriptions(db)
    await db.refresh(member)

    assert await balance_of(db, member, currency) == 7


async def test_what_ends_with_the_subscription_is_the_entitlement_and_not_what_it_gave(db, subscribed, tenant, member):
    """Access is what stops: the door closes, and what the account already took through it stays."""
    owned = await expired_holding(db, subscribed, tenant, member, cadence=BenefitCadence.ON_ACTIVATION)

    entitlement = (await db.execute(select(UserEntitlement).where(UserEntitlement.subscription_id == subscribed["subscription"].id))).scalars().one()

    assert entitlement.status == UserEntitlementStatus.EXPIRED
    assert owned.product_id


async def test_a_plan_carrying_every_kind_of_benefit_delivers_all_of_them_in_one_activation(db, subscribed, member, tenant, currency):
    """A plan is a bundle, so what proves it works is the bundle arriving whole and not each piece on its own."""
    product = await make_product(db, tenant)

    await make_benefit(db, subscribed["entitlement"], type=BenefitType.ACCESS, target="premium")
    gems = await make_currency(db, code="gem", name="Gems")

    await make_benefit(db, subscribed["entitlement"], type=BenefitType.CREDIT, currency_id=currency.id, target="coins", quantity=50)
    await make_benefit(db, subscribed["entitlement"], type=BenefitType.CREDIT, currency_id=gems.id, target="gems", quantity=10)
    await make_benefit(db, subscribed["entitlement"], type=BenefitType.PRODUCT, target="handbook", quantity=1, product_id=product.id)

    grants = await delivery_service.activate(db, subscribed["subscription"])

    await db.refresh(member)

    entitlement = await db.scalar(select(UserEntitlement).where(UserEntitlement.subscription_id == subscribed["subscription"].id))
    owned = (await db.execute(select(UserProduct))).scalars().all()

    assert len(grants) == 4
    assert {grant.status for grant in grants} == {BenefitGrantStatus.COMPLETED}
    assert entitlement.status == UserEntitlementStatus.ACTIVE
    assert await balance_of(db, member, currency) == 50
    assert await balance_of(db, member, gems) == 10
    assert [row.product_id for row in owned] == [product.id]


async def test_an_access_benefit_is_what_turns_the_entitlement_on(db, subscribed):
    """The grant says it was delivered, and the entitlement is what an app actually gates by."""
    entitlement = await db.scalar(select(UserEntitlement).where(UserEntitlement.subscription_id == subscribed["subscription"].id))

    assert entitlement is None

    await make_benefit(db, subscribed["entitlement"], type=BenefitType.ACCESS, target="premium")
    await delivery_service.activate(db, subscribed["subscription"])

    entitlement = await db.scalar(select(UserEntitlement).where(UserEntitlement.subscription_id == subscribed["subscription"].id))

    assert entitlement.status == UserEntitlementStatus.ACTIVE
    assert entitlement.revoked_at is None


async def test_a_credit_benefit_leaves_the_ledger_entry_that_explains_the_wallet(db, subscribed, member, currency):
    """The wallet is the running total of the ledger, so a delivery that moved one without the other would be a balance nobody can account for."""
    await make_benefit(db, subscribed["entitlement"], type=BenefitType.CREDIT, currency_id=currency.id, target="gold", quantity=50)

    grants = await delivery_service.activate(db, subscribed["subscription"])

    await db.refresh(member)

    entries = (await db.execute(select(CreditTransaction).where(CreditTransaction.user_id == member.id))).scalars().all()

    assert len(entries) == 1
    assert entries[0].amount == 50
    assert entries[0].balance_after == await balance_of(db, member, currency)
    assert entries[0].currency_id == currency.id
    assert grants[0].result["balance_after"] == entries[0].balance_after


async def test_the_same_cycle_never_pays_the_wallet_twice(db, subscribed, member, currency):
    """The grant key is the idempotency of the ledger too, so a reprocessed pass leaves the balance where it was."""
    await make_benefit(db, subscribed["entitlement"], type=BenefitType.CREDIT, currency_id=currency.id, target="gold", quantity=50)

    await delivery_service.activate(db, subscribed["subscription"])
    await delivery_service.activate(db, subscribed["subscription"])

    await db.refresh(member)

    entries = (await db.execute(select(CreditTransaction).where(CreditTransaction.user_id == member.id))).scalars().all()

    assert await balance_of(db, member, currency) == 50
    assert len(entries) == 1


async def test_a_cycle_another_node_already_claimed_is_read_instead_of_erroring(db, subscribed, currency):
    """Two instances carrying the same cron tag fire the same job, and the grant key is what keeps one cycle to one delivery."""
    await make_benefit(db, subscribed["entitlement"], type=BenefitType.CREDIT, currency_id=currency.id, target="gold", quantity=5)
    await delivery_service.activate(db, subscribed["subscription"])

    grant = (await db.execute(select(BenefitGrant))).scalars().one()
    twin = BenefitGrant(subscription_benefit_id=grant.subscription_benefit_id, grant_key=grant.grant_key, cycle_key=grant.cycle_key, scheduled_at=grant.scheduled_at, status=BenefitGrantStatus.PROCESSING, requested_quantity=1, attempts=1)

    settled = await delivery_service.claim(db, twin, grant.grant_key)

    assert settled.id == grant.id
    assert len((await db.execute(select(BenefitGrant))).scalars().all()) == 1


async def test_a_cycle_the_node_lost_is_not_delivered_twice(db, subscribed, monkeypatch, currency):
    """The loser of the race hands back the winner's grant and delivers nothing, or the cycle would pay out twice."""
    benefit = await make_benefit(db, subscribed["entitlement"], type=BenefitType.CREDIT, currency_id=currency.id, target="gold", quantity=5)
    winner = BenefitGrant(subscription_benefit_id=1, grant_key="ja-era", cycle_key="c", status=BenefitGrantStatus.COMPLETED, requested_quantity=1, attempts=1)

    async def lost(self, db, grant, grant_key):
        return winner

    monkeypatch.setattr(type(delivery_service), "claim", lost)

    grants = await delivery_service.activate(db, subscribed["subscription"])

    assert benefit.id
    assert grants == [winner]
    assert await db.scalar(select(CreditTransaction).where(CreditTransaction.user_id == subscribed["subscription"].user_id)) is None


async def test_a_subscription_that_comes_back_delivers_again(db, subscribed, currency):
    """A refund reversed, or a provider reporting active again, would otherwise return the entitlement and never the benefit."""
    await make_benefit(db, subscribed["entitlement"], type=BenefitType.CREDIT, currency_id=currency.id, target="gold", quantity=5, cadence=BenefitCadence.RECURRING, interval_unit=IntervalUnit.MONTH, interval_value=1)

    subscription = subscribed["subscription"]
    await delivery_service.activate(db, subscription)
    await delivery_service.end_benefits(db, subscription)
    await db.commit()

    ended = (await db.execute(select(SubscriptionBenefit))).scalars().one()

    assert ended.status == BenefitStatus.ENDED

    await delivery_service.activate(db, subscription)
    await db.refresh(ended)

    assert ended.status == BenefitStatus.ACTIVE
    assert ended.next_grant_at is not None


async def test_an_entitlement_another_activation_already_wrote_is_read_instead_of_erroring(db, subscribed, monkeypatch):
    """A purchase reaches here by the webhook and by the app's refresh at the same second, and both activate the same subscription."""
    subscription = subscribed["subscription"]

    original = type(delivery_service).entitlements_of
    missed = []

    async def blind_once(self, session, target):
        if missed:
            return await original(self, session, target)

        missed.append(True)

        session.add(UserEntitlement(subscription_id=target.id, entitlement_id=subscribed["entitlement"].id, status=UserEntitlementStatus.ACTIVE, started_at=now()))
        await session.commit()

        return {}

    monkeypatch.setattr(type(delivery_service), "entitlements_of", blind_once)

    await delivery_service.activate(db, subscription)

    rows = (await db.execute(select(UserEntitlement).where(UserEntitlement.subscription_id == subscription.id))).scalars().all()

    assert len(rows) == 1
    assert rows[0].status == UserEntitlementStatus.ACTIVE


async def test_a_benefit_another_activation_already_snapshot_is_read_instead_of_erroring(db, subscribed, monkeypatch, currency):
    """The same two callers reach the snapshot, and one row per benefit is what a subscription keeps."""
    benefit = await make_benefit(db, subscribed["entitlement"], type=BenefitType.CREDIT, currency_id=currency.id, target="gold", quantity=5)

    original = type(delivery_service).benefits_of
    missed = []

    async def blind_once(self, session, target):
        if missed:
            return await original(self, session, target)

        missed.append(True)

        entitlement = (await session.execute(select(UserEntitlement).where(UserEntitlement.subscription_id == target.id))).scalars().one()

        session.add(SubscriptionBenefit(subscription_id=target.id, benefit_id=benefit.id, user_entitlement_id=entitlement.id, status=BenefitStatus.ACTIVE, benefit_type=benefit.type, target=benefit.target, quantity=benefit.quantity, cadence=benefit.cadence, anchor_at=now(), next_grant_at=now()))
        await session.commit()

        return {}

    monkeypatch.setattr(type(delivery_service), "benefits_of", blind_once)

    await delivery_service.activate(db, subscribed["subscription"])

    rows = (await db.execute(select(SubscriptionBenefit).where(SubscriptionBenefit.subscription_id == subscribed["subscription"].id))).scalars().all()

    assert len(rows) == 1


async def test_a_trial_hands_out_access_and_holds_back_what_outlives_it(db, tenant, member, currency):
    """The plan says access_only during a trial, so the door opens and nothing is given away for good."""
    plan = await make_plan(db, tenant, trial_benefit_policy=BenefitPolicy.ACCESS_ONLY)
    entitlement = await make_entitlement(db, tenant)

    await make_plan_entitlement(db, plan, entitlement)
    await make_benefit(db, entitlement, type=BenefitType.ACCESS, target="access", quantity=1)
    await make_benefit(db, entitlement, type=BenefitType.CREDIT, currency_id=currency.id, target="gold", quantity=5)

    subscription = await make_subscription(db, tenant, member, plan, status=SubscriptionStatus.TRIALING)
    grants = await delivery_service.activate(db, subscription)

    by_reason = {grant.status: grant.error_code for grant in grants}

    assert BenefitGrantStatus.COMPLETED in by_reason
    assert by_reason[BenefitGrantStatus.SKIPPED] == "withheld_by_plan_policy"
    assert (await db.execute(select(CreditTransaction))).scalars().all() == []


async def test_a_trial_a_plan_opened_to_everything_delivers_everything(db, tenant, member, currency):
    plan = await make_plan(db, tenant, trial_benefit_policy=BenefitPolicy.ALL)
    entitlement = await make_entitlement(db, tenant)

    await make_plan_entitlement(db, plan, entitlement)
    await make_benefit(db, entitlement, type=BenefitType.CREDIT, currency_id=currency.id, target="gold", quantity=5)

    subscription = await make_subscription(db, tenant, member, plan, status=SubscriptionStatus.TRIALING)
    grants = await delivery_service.activate(db, subscription)

    assert grants[0].status == BenefitGrantStatus.COMPLETED
    assert len((await db.execute(select(CreditTransaction))).scalars().all()) == 1


async def test_a_plan_that_promises_nothing_in_grace_delivers_nothing(db, tenant, member):
    plan = await make_plan(db, tenant, grace_benefit_policy=BenefitPolicy.NONE)
    entitlement = await make_entitlement(db, tenant)

    await make_plan_entitlement(db, plan, entitlement)
    await make_benefit(db, entitlement, type=BenefitType.ACCESS, target="access", quantity=1)

    subscription = await make_subscription(db, tenant, member, plan, status=SubscriptionStatus.GRACE_PERIOD)
    grants = await delivery_service.activate(db, subscription)

    assert grants[0].status == BenefitGrantStatus.SKIPPED
    assert grants[0].error_code == "withheld_by_plan_policy"


async def test_a_paying_subscription_is_never_narrowed_by_a_policy(db, subscribed, currency):
    """The two policies speak about a trial and a grace period, and an active subscription is neither."""
    await make_benefit(db, subscribed["entitlement"], type=BenefitType.CREDIT, currency_id=currency.id, target="gold", quantity=5)

    grants = await delivery_service.activate(db, subscribed["subscription"])

    assert grants[0].status == BenefitGrantStatus.COMPLETED


async def test_a_benefit_taken_out_of_the_catalog_is_not_promised_to_a_new_subscription(db, subscribed, currency):
    """Turning a benefit off is how an operator stops promising it, and a snapshot that ignored that would keep paying it out."""
    await make_benefit(db, subscribed["entitlement"], type=BenefitType.CREDIT, currency_id=currency.id, target="gold", quantity=5, active=False)
    await make_benefit(db, subscribed["entitlement"], type=BenefitType.ACCESS, target="access", quantity=1)

    await delivery_service.activate(db, subscribed["subscription"])

    snapshots = (await db.execute(select(SubscriptionBenefit))).scalars().all()

    assert [snapshot.benefit_type for snapshot in snapshots] == [BenefitType.ACCESS]
