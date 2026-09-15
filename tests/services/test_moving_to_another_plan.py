from enums.subscription import BenefitStatus, BenefitType, UserEntitlementStatus
from services.delivery import delivery_service
from tests.factories import make_benefit, make_entitlement, make_plan, make_plan_entitlement, make_subscription


async def test_moving_to_another_plan_keeps_only_what_the_plan_it_is_on_now_promises(db, tenant, member):
    monthly = await make_plan(db, tenant, code="monthly")
    annual = await make_plan(db, tenant, code="annual")

    for plan, code in ((monthly, "monthly-access"), (annual, "annual-access")):
        entitlement = await make_entitlement(db, tenant, code=code)
        await make_plan_entitlement(db, plan, entitlement)
        await make_benefit(db, entitlement, type=BenefitType.ACCESS, target=code)

    subscription = await make_subscription(db, tenant, member, monthly)
    await delivery_service.activate(db, subscription)

    subscription.plan_id = annual.id
    await delivery_service.activate(db, subscription)

    benefits = await delivery_service.benefits_of(db, subscription)
    entitlements = await delivery_service.entitlements_of(db, subscription)

    assert sorted((benefit.target, benefit.status.value) for benefit in benefits.values()) == [("annual-access", BenefitStatus.ACTIVE.value), ("monthly-access", BenefitStatus.ENDED.value)]
    assert sorted(row.status.value for row in entitlements.values()) == sorted([UserEntitlementStatus.ACTIVE.value, UserEntitlementStatus.EXPIRED.value])
