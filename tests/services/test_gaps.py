import pytest

from enums.subscription import BenefitCadence, BenefitType, IntervalUnit
from helpers.errors import ValidationError
from models.subscription import SubscriptionBenefit
from services.delivery import delivery_service
from services.gallery import gallery_service
from services.subscription import benefit_service, plan_service
from tests.factories import make_benefit, make_entitlement, make_plan, make_plan_entitlement, make_subscription


async def test_a_plan_edit_that_leaves_the_code_alone_skips_the_uniqueness_check(db, tenant):
    plan = await make_plan(db, tenant)

    updated = await plan_service.update(db, plan.id, {"name": "Renamed"})

    assert updated.code == "monthly"


async def test_a_recurring_benefit_refuses_an_interval_below_one(db):
    entitlement = await make_entitlement(db)

    payload = {"entitlement_id": entitlement.id, "type": BenefitType.ACCESS, "target": "reader", "cadence": BenefitCadence.RECURRING, "interval_unit": IntervalUnit.MONTH, "interval_value": 0}

    with pytest.raises(ValidationError) as error:
        await benefit_service.create(db, payload)

    assert error.value.code == "error.benefit-recurring-requires-interval"


def test_the_interval_rule_refuses_a_negative_value():
    with pytest.raises(ValidationError) as error:
        benefit_service.validate_interval(BenefitCadence.RECURRING, IntervalUnit.MONTH, -1)

    assert error.value.code == "error.benefit-interval-value-min"


async def test_running_the_same_cycle_twice_answers_the_first_grant(db, tenant, member):
    plan = await make_plan(db, tenant)
    entitlement = await make_entitlement(db, tenant)

    await make_plan_entitlement(db, plan, entitlement)
    await make_benefit(db, entitlement)

    subscription = await make_subscription(db, tenant, member, plan)

    await delivery_service.activate(db, subscription)

    snapshot = (await db.execute(SubscriptionBenefit.__table__.select())).first()
    benefit = await db.get(SubscriptionBenefit, snapshot.id)

    first = await delivery_service.run_cycle(db, benefit, f"activation:{benefit.cycle}", benefit.anchor_at)
    second = await delivery_service.run_cycle(db, benefit, f"activation:{benefit.cycle}", benefit.anchor_at)

    assert first.id == second.id


async def test_a_listing_answers_one_row_per_tag_in_the_language_the_page_is_in(db, tenant):
    """A card that shows one title and opens another is worse than no card, so the listing answers what the tag would open."""
    from tests.factories import make_gallery, make_language

    english = await make_language(db, code_iso_639_1="en", name="English")
    portuguese = await make_language(db, code_iso_639_1="pt", name="Português")

    await make_gallery(db, tenant, tag="office", title="Our office", language_id=english.id)
    await make_gallery(db, tenant, tag="office", title="Nosso escritório", language_id=portuguese.id)

    listed = await gallery_service.list_reachable(db, tenant.id, "pt")

    assert [gallery.title for gallery in listed] == ["Nosso escritório"]
    assert (await gallery_service.find_by_tag(db, "office", tenant.id, "pt")).title == "Nosso escritório"

    assert [gallery.title for gallery in await gallery_service.list_reachable(db, tenant.id, "en")] == ["Our office"]


async def test_a_sitemap_never_offers_the_same_address_twice(site, db, tenant):
    """The URL carries the tag and not the language, so two rows of one tag are one page and one entry."""
    from tests.factories import make_content, make_language

    english = await make_language(db, code_iso_639_1="en", name="English")
    portuguese = await make_language(db, code_iso_639_1="pt", name="Português")

    await make_content(db, tenant, tag="terms", title="Terms", language_id=english.id)
    await make_content(db, tenant, tag="terms", title="Termos", language_id=portuguese.id)

    body = (await site.get("/sitemap.xml")).text

    assert body.count("<loc>http://acme.test/content/terms</loc>") == 1
