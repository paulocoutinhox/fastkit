import secrets
from datetime import timedelta
from decimal import Decimal

import pytest
import pytest_asyncio

from enums.integration import NormalizedAction, WebhookEventStatus
from enums.subscription import BenefitCadence, BenefitType, IntervalUnit
from helpers.dates import now
from models.integration import WebhookEvent
from services.checkout import checkout_service
from services.delivery import delivery_service
from tests.factories import make_benefit, make_entitlement, make_integration, make_language, make_plan, make_plan_entitlement, make_product, make_subscription, save


async def test_plan_derives_the_code_and_belongs_to_one_tenant(client, tenant, admin_headers):
    response = await client.post("/api/plans", json={"tenantId": tenant.id, "name": "Monthly Plan", "resumeDeliveryPolicy": "same_cycle"}, headers=admin_headers)

    assert response.status_code == 201
    assert response.json()["code"] == "monthly-plan"
    assert response.json()["tenant"]["code"] == tenant.code


async def test_plan_code_is_unique_inside_the_tenant(client, db, tenant, admin_headers):
    await make_plan(db, tenant)

    response = await client.post("/api/plans", json={"tenantId": tenant.id, "code": "monthly", "name": "Other", "resumeDeliveryPolicy": "same_cycle"}, headers=admin_headers)

    assert response.status_code == 422
    assert response.json()["code"] == "error.code-already-used"


async def test_plan_code_may_repeat_across_tenants(client, db, tenant, admin_headers):
    await make_plan(db, tenant)

    other = await client.post("/api/tenants", json={"name": "Other", "domain": "other.example.org"}, headers=admin_headers)
    response = await client.post("/api/plans", json={"tenantId": other.json()["id"], "code": "monthly", "name": "Monthly", "resumeDeliveryPolicy": "same_cycle"}, headers=admin_headers)

    assert response.status_code == 201


async def test_entitlement_lifecycle(client, admin_headers):
    created = await client.post("/api/entitlements", json={"code": "reader", "name": "Reader"}, headers=admin_headers)

    assert created.status_code == 201

    updated = await client.put(f"/api/entitlements/{created.json()['id']}", json={"name": "Reader Plus"}, headers=admin_headers)

    assert updated.json()["name"] == "Reader Plus"

    assert (await client.delete(f"/api/entitlements/{created.json()['id']}", headers=admin_headers)).status_code == 204


def build_benefit(entitlement_id: int, **overrides) -> dict:
    return {"entitlement_id": entitlement_id, "type": BenefitType.ACCESS, "target": "reader", "cadence": BenefitCadence.ON_ACTIVATION} | overrides


async def test_benefit_recurring_requires_an_interval(client, db, admin_headers):
    entitlement = await make_entitlement(db)

    response = await client.post("/api/benefits", json=build_benefit(entitlement.id, cadence=BenefitCadence.RECURRING), headers=admin_headers)

    assert response.status_code == 422
    assert response.json()["code"] == "error.benefit-recurring-requires-interval"


async def test_benefit_non_recurring_refuses_an_interval(client, db, admin_headers):
    entitlement = await make_entitlement(db)

    payload = build_benefit(entitlement.id, interval_unit=IntervalUnit.MONTH, interval_value=1)
    response = await client.post("/api/benefits", json=payload, headers=admin_headers)

    assert response.status_code == 422
    assert response.json()["code"] == "error.benefit-non-recurring-no-interval"


async def test_benefit_credit_requires_a_positive_quantity(client, db, admin_headers):
    """Zero is a number a quantity may be and never one a credit benefit may hand over, which is the half the service owns."""
    entitlement = await make_entitlement(db)

    payload = build_benefit(entitlement.id, type=BenefitType.CREDIT, target="gold", quantity=0)
    response = await client.post("/api/benefits", json=payload, headers=admin_headers)

    assert response.status_code == 422
    assert response.json()["code"] == "error.benefit-quantity-must-be-positive"


@pytest.mark.parametrize("quantity", [-1, 10**30])
async def test_a_benefit_quantity_is_a_number_the_column_can_hold(client, db, admin_headers, quantity):
    """A quantity is a magnitude whatever the benefit is, and one past the column reached the driver instead of being refused."""
    entitlement = await make_entitlement(db)

    payload = build_benefit(entitlement.id, type=BenefitType.ACCESS, target="door", quantity=quantity)

    assert (await client.post("/api/benefits", json=payload, headers=admin_headers)).status_code == 422


async def test_benefit_credit_requires_a_currency(client, db, admin_headers):
    entitlement = await make_entitlement(db)

    payload = build_benefit(entitlement.id, type=BenefitType.CREDIT, target="bronze", quantity=5)
    response = await client.post("/api/benefits", json=payload, headers=admin_headers)

    assert response.status_code == 422
    assert response.json()["code"] == "error.benefit-credit-requires-currency"


async def test_benefit_product_requires_a_product(client, db, admin_headers):
    entitlement = await make_entitlement(db)

    payload = build_benefit(entitlement.id, type=BenefitType.PRODUCT, target="handbook", quantity=1)
    response = await client.post("/api/benefits", json=payload, headers=admin_headers)

    assert response.status_code == 422
    assert response.json()["code"] == "error.benefit-product-requires-product"


async def test_benefit_product_with_a_product_is_accepted(client, db, tenant, admin_headers):
    entitlement = await make_entitlement(db, tenant)
    product = await make_product(db, tenant)

    payload = build_benefit(entitlement.id, type=BenefitType.PRODUCT, target="handbook", quantity=1, product_id=product.id)
    response = await client.post("/api/benefits", json=payload, headers=admin_headers)

    assert response.status_code == 201
    assert response.json()["target"] == "handbook"


async def test_a_product_never_hangs_off_a_benefit_of_another_kind(client, db, tenant, admin_headers):
    """A product on an access benefit is a promise nothing delivers, so it is refused where it is written."""
    entitlement = await make_entitlement(db, tenant)
    product = await make_product(db, tenant)

    payload = build_benefit(entitlement.id, type=BenefitType.ACCESS, target="access", quantity=1, product_id=product.id)
    response = await client.post("/api/benefits", json=payload, headers=admin_headers)

    assert response.status_code == 422
    assert response.json()["code"] == "error.benefit-product-only-on-a-product-benefit"


async def test_benefit_recurring_with_an_interval_is_accepted(client, db, admin_headers):
    entitlement = await make_entitlement(db)

    payload = build_benefit(entitlement.id, cadence=BenefitCadence.RECURRING, interval_unit=IntervalUnit.MONTH, interval_value=1)
    response = await client.post("/api/benefits", json=payload, headers=admin_headers)

    assert response.status_code == 201


async def test_mine_answers_only_the_subscriptions_of_the_caller(client, db, tenant, member, member_headers):
    plan = await make_plan(db, tenant)

    await make_subscription(db, tenant, member, plan)

    response = await client.get("/api/subscriptions/me", headers=member_headers)

    assert response.status_code == 200
    assert len(response.json()["items"]) == 1


async def test_activate_delivers_what_the_subscription_owes(client, db, tenant, member, admin_headers):
    plan = await make_plan(db, tenant)
    entitlement = await make_entitlement(db, tenant)

    await make_plan_entitlement(db, plan, entitlement)
    await make_benefit(db, entitlement)

    subscription = await make_subscription(db, tenant, member, plan)

    response = await client.post(f"/api/subscriptions/{subscription.id}/activate", headers=admin_headers)

    assert response.status_code == 200
    assert response.json() == {"granted": 1}


async def test_activate_requires_an_administrator(client, db, tenant, member, member_headers):
    plan = await make_plan(db, tenant)
    subscription = await make_subscription(db, tenant, member, plan)

    assert (await client.post(f"/api/subscriptions/{subscription.id}/activate", headers=member_headers)).status_code == 403


async def test_the_transactions_of_a_subscription_are_what_the_provider_reported(client, db, tenant, member, member_headers):
    plan = await make_plan(db, tenant)
    subscription = await make_subscription(db, tenant, member, plan)
    integration = await make_integration(db, tenant)

    await save(db, WebhookEvent(tenant_id=tenant.id, integration_id=integration.id, subscription_id=subscription.id, external_event_id="a", action=NormalizedAction.RENEW, status=WebhookEventStatus.COMPLETED, payload_hash="a", payload={}, meta={}))
    await save(db, WebhookEvent(tenant_id=tenant.id, integration_id=integration.id, subscription_id=subscription.id, external_event_id="b", action=NormalizedAction.EXPIRE, status=WebhookEventStatus.FAILED, payload_hash="b", payload={}, meta={}))

    listed = (await client.get(f"/api/subscriptions/{subscription.id}/transactions", headers=member_headers)).json()

    assert sorted(item["action"] for item in listed["items"]) == ["expire", "renew"]


async def test_the_transactions_of_somebody_else_are_not_answered(client, db, tenant, member, administrator, admin_headers):
    """A subscription that is not the caller's is one that does not exist, or an empty answer would read as one with no payments yet."""
    plan = await make_plan(db, tenant)
    subscription = await make_subscription(db, tenant, member, plan)

    assert (await client.get(f"/api/subscriptions/{subscription.id}/transactions", headers=admin_headers)).status_code == 404


async def test_a_subscription_is_never_created_or_edited_from_the_admin(client, db, tenant, member, admin_headers):
    """A subscription is what the provider says it is, and a form left open for a month would write a stale one."""
    plan = await make_plan(db, tenant)
    subscription = await make_subscription(db, tenant, member, plan)

    assert (await client.post("/api/subscriptions", json={"tenantId": tenant.id, "userId": member.id, "planId": plan.id}, headers=admin_headers)).status_code == 405
    assert (await client.put(f"/api/subscriptions/{subscription.id}", json={"status": "active"}, headers=admin_headers)).status_code == 405
    assert (await client.delete(f"/api/subscriptions/{subscription.id}", headers=admin_headers)).status_code == 405


async def test_a_subscription_is_still_read_and_activated_from_the_admin(client, db, tenant, member, admin_headers):
    plan = await make_plan(db, tenant)
    subscription = await make_subscription(db, tenant, member, plan)

    assert (await client.get(f"/api/subscriptions/{subscription.id}", headers=admin_headers)).status_code == 200
    assert (await client.post(f"/api/subscriptions/{subscription.id}/activate", headers=admin_headers)).status_code == 200


@pytest_asyncio.fixture
async def delivered(db, tenant, member, administrator):
    """One subscription of each of two people, both already activated."""
    plan = await make_plan(db, tenant)
    entitlement = await make_entitlement(db, tenant)

    await make_plan_entitlement(db, plan, entitlement)
    await make_benefit(db, entitlement, grant_on_activation=True)

    mine = await make_subscription(db, tenant, member, plan)
    theirs = await make_subscription(db, tenant, administrator, plan)

    await delivery_service.activate(db, mine)
    await delivery_service.activate(db, theirs)

    return {"mine": mine, "theirs": theirs}


@pytest.mark.parametrize("resource", ["user-entitlements", "subscription-benefits", "benefit-grants"])
async def test_what_a_subscription_produced_is_filtered_by_the_person(client, delivered, member, admin_headers, resource):
    """A row number means nothing to whoever is looking, and the person is what they came in knowing."""
    listed = (await client.get(f"/api/{resource}?userId={member.id}", headers=admin_headers)).json()

    assert listed["count"] == 1


@pytest.mark.parametrize("resource", ["user-entitlements", "subscription-benefits", "benefit-grants"])
async def test_without_a_person_everything_that_was_produced_is_listed(client, delivered, admin_headers, resource):
    assert (await client.get(f"/api/{resource}", headers=admin_headers)).json()["count"] == 2


async def test_a_transaction_carries_what_was_paid_and_in_which_currency(client, db, tenant, member, member_headers):
    """The store decides the price per region, so the amount only exists once somebody actually paid it."""
    plan = await make_plan(db, tenant)
    subscription = await make_subscription(db, tenant, member, plan)
    integration = await make_integration(db, tenant)

    db.add(WebhookEvent(tenant_id=tenant.id, integration_id=integration.id, subscription_id=subscription.id, external_event_id="evt-1", payload_hash="h", status=WebhookEventStatus.COMPLETED, amount=Decimal("19.90"), currency="BRL", payload={}, meta={}))
    await db.commit()

    items = (await client.get(f"/api/subscriptions/{subscription.id}/transactions", headers=member_headers)).json()["items"]

    assert Decimal(items[0]["amount"]) == Decimal("19.90")
    assert items[0]["currency"] == "BRL"


async def test_a_transaction_the_provider_priced_in_nothing_answers_no_amount(client, db, tenant, member, member_headers):
    plan = await make_plan(db, tenant)
    subscription = await make_subscription(db, tenant, member, plan)
    integration = await make_integration(db, tenant)

    db.add(WebhookEvent(tenant_id=tenant.id, integration_id=integration.id, subscription_id=subscription.id, external_event_id="evt-2", payload_hash="h", status=WebhookEventStatus.COMPLETED, payload={}, meta={}))
    await db.commit()

    items = (await client.get(f"/api/subscriptions/{subscription.id}/transactions", headers=member_headers)).json()["items"]

    assert items[0]["amount"] is None
    assert items[0]["currency"] is None


async def test_what_the_admin_activates_is_what_the_app_reads_as_access(client, db, tenant, member, member_headers, admin_headers):
    """The delivery engine and the endpoint an app gates by are two ends of one wire, and only reading both proves it is connected."""
    plan = await make_plan(db, tenant)
    entitlement = await make_entitlement(db, tenant, code="premium", name="Premium")

    await make_plan_entitlement(db, plan, entitlement)
    await make_benefit(db, entitlement, type=BenefitType.ACCESS, target="premium")

    subscription = await make_subscription(db, tenant, member, plan)

    assert (await client.get("/api/account/entitlements", headers=member_headers)).json()["items"] == []

    await client.post(f"/api/subscriptions/{subscription.id}/activate", headers=admin_headers)

    items = (await client.get("/api/account/entitlements", headers=member_headers)).json()["items"]

    assert [item["code"] for item in items] == ["premium"]
    assert items[0]["status"] == "active"


async def test_an_expired_subscription_takes_the_access_back_from_the_app(client, db, tenant, member, member_headers, admin_headers):
    plan = await make_plan(db, tenant)
    entitlement = await make_entitlement(db, tenant, code="premium", name="Premium")

    await make_plan_entitlement(db, plan, entitlement)
    await make_benefit(db, entitlement, type=BenefitType.ACCESS, target="premium")

    subscription = await make_subscription(db, tenant, member, plan, access_until=now() - timedelta(days=1))

    await client.post(f"/api/subscriptions/{subscription.id}/activate", headers=admin_headers)
    await delivery_service.expire_subscriptions(db)

    items = (await client.get("/api/account/entitlements", headers=member_headers)).json()["items"]

    assert items[0]["status"] == "expired"


async def test_a_benefit_never_hands_over_the_product_of_another_tenant(client, db, tenant, admin_headers):
    """The form narrows the list, and this is the half that refuses what somebody sent anyway."""
    from tests.factories import make_tenant

    entitlement = await make_entitlement(db, tenant)
    outsider = await make_product(db, await make_tenant(db, code="other", domain="other.test"))

    payload = build_benefit(entitlement.id, type=BenefitType.PRODUCT, target="handbook", quantity=1, product_id=outsider.id)
    response = await client.post("/api/benefits", json=payload, headers=admin_headers)

    assert response.status_code == 422
    assert response.json()["code"] == "error.product-out-of-tenant"


async def test_a_shared_product_is_handed_over_by_any_entitlement(client, db, tenant, admin_headers):
    entitlement = await make_entitlement(db, tenant)
    shared = await make_product(db)

    payload = build_benefit(entitlement.id, type=BenefitType.PRODUCT, target="handbook", quantity=1, product_id=shared.id)

    assert (await client.post("/api/benefits", json=payload, headers=admin_headers)).status_code == 201


async def test_the_same_plan_is_sold_once_per_language(client, db, tenant, admin_headers):
    """A price is written in the currency of a market, so one code answers once for each language it is read in."""
    english = await make_language(db, code_iso_639_1="en", name="English")
    portuguese = await make_language(db, code_iso_639_1="pt", name="Português")

    await make_plan(db, tenant, language_id=english.id)

    response = await client.post("/api/plans", json={"tenantId": tenant.id, "languageId": portuguese.id, "code": "monthly", "name": "Mensal", "currency": "BRL", "price": "99.90", "resumeDeliveryPolicy": "same_cycle"}, headers=admin_headers)

    assert response.status_code == 201
    assert response.json()["language"]["name"] == "Português"


async def test_the_same_plan_is_never_sold_twice_in_one_language(client, db, tenant, admin_headers):
    english = await make_language(db, code_iso_639_1="en", name="English")
    await make_plan(db, tenant, language_id=english.id)

    response = await client.post("/api/plans", json={"tenantId": tenant.id, "languageId": english.id, "code": "monthly", "name": "Other", "resumeDeliveryPolicy": "same_cycle"}, headers=admin_headers)

    assert response.status_code == 422
    assert response.json()["code"] == "error.code-already-used"


async def test_a_plan_naming_no_language_is_a_scope_of_its_own(client, db, tenant, admin_headers):
    """No null equals another in a plain unique index, and two plans of one code answering everybody would be a coin toss."""
    await make_plan(db, tenant)

    response = await client.post("/api/plans", json={"tenantId": tenant.id, "code": "monthly", "name": "Other", "resumeDeliveryPolicy": "same_cycle"}, headers=admin_headers)

    assert response.status_code == 422
    assert response.json()["code"] == "error.code-already-used"


async def test_the_paywall_is_priced_in_the_currency_of_whoever_reads_it(client, db, tenant, tenant_headers):
    english = await make_language(db, code_iso_639_1="en", name="English")
    portuguese = await make_language(db, code_iso_639_1="pt", name="Português")

    await make_plan(db, tenant, language_id=english.id, name="Monthly", currency="USD", price=Decimal("19.90"))
    await make_plan(db, tenant, language_id=portuguese.id, name="Mensal", currency="BRL", price=Decimal("99.90"))

    brazilian = await client.get("/api/subscriptions/plans", headers=tenant_headers | {"accept-language": "pt-BR,pt;q=0.9"})

    assert [(plan["name"], plan["currency"]) for plan in brazilian.json()["items"]] == [("Mensal", "BRL")]

    reader = await client.get("/api/subscriptions/plans", headers=tenant_headers | {"accept-language": "en"})

    assert [(plan["name"], plan["currency"]) for plan in reader.json()["items"]] == [("Monthly", "USD")]


async def test_a_language_nothing_was_written_in_is_answered_in_english(client, db, tenant, tenant_headers):
    """English answers for what a language does not have, so a paywall is never an empty page."""
    english = await make_language(db, code_iso_639_1="en", name="English")
    await make_language(db, code_iso_639_1="es", name="Español")

    await make_plan(db, tenant, language_id=english.id, name="Monthly")

    answer = await client.get("/api/subscriptions/plans", headers=tenant_headers | {"accept-language": "es"})

    assert [plan["name"] for plan in answer.json()["items"]] == ["Monthly"]


async def test_the_paywall_answers_one_row_per_code(client, db, tenant, tenant_headers):
    english = await make_language(db, code_iso_639_1="en", name="English")
    portuguese = await make_language(db, code_iso_639_1="pt", name="Português")

    await make_plan(db, tenant, code="yearly", language_id=english.id, name="Yearly", position=1)
    await make_plan(db, tenant, code="yearly", language_id=portuguese.id, name="Anual", position=1)
    await make_plan(db, tenant, code="monthly", language_id=english.id, name="Monthly", position=0)

    answer = await client.get("/api/subscriptions/plans", headers=tenant_headers | {"accept-language": "pt"})

    assert [plan["code"] for plan in answer.json()["items"]] == ["monthly", "yearly"]
    assert [plan["name"] for plan in answer.json()["items"]] == ["Monthly", "Anual"]


async def test_paying_for_a_plan_pays_for_the_one_that_was_shown(client, db, tenant, member_headers, monkeypatch):
    """The row a checkout opens is the row the reader was priced at, and never the one another market was."""
    english = await make_language(db, code_iso_639_1="en", name="English")
    portuguese = await make_language(db, code_iso_639_1="pt", name="Português")

    await make_plan(db, tenant, language_id=english.id, name="Monthly", currency="USD")
    brazilian = await make_plan(db, tenant, language_id=portuguese.id, name="Mensal", currency="BRL")
    opened = []

    async def record(session, tenant_row, user, plan, success_url, cancel_url):
        opened.append(plan.id)

        return "https://gateway.acme.com/session"

    monkeypatch.setattr(checkout_service, "for_plan", record)

    answer = await client.post("/api/subscriptions/plans/monthly/checkout", json={"successUrl": "https://acme.com/ok", "cancelUrl": "https://acme.com/no"}, headers=member_headers | {"accept-language": "pt", "x-tenant-code": tenant.code})

    assert answer.status_code == 200
    assert opened == [brazilian.id]


async def test_what_a_provider_reported_is_paged_like_every_other_listing(client, db, tenant, member, member_headers):
    """A subscription of a chatty gateway holds a row per notice, so the listing answers a page and never the lot."""
    plan = await make_plan(db, tenant)
    integration = await make_integration(db, tenant)
    subscription = await make_subscription(db, tenant, member, plan, integration_id=integration.id)

    for _ in range(3):
        await save(
            db,
            WebhookEvent(
                tenant_id=tenant.id, integration_id=integration.id, subscription_id=subscription.id, user_id=member.id, external_event_id=f"evt-{secrets.token_hex(4)}", payload_hash=secrets.token_hex(16), status=WebhookEventStatus.COMPLETED, action=NormalizedAction.RENEW, occurred_at=now(), payload={}, meta={}
            ),
        )

    first = await client.get(f"/api/subscriptions/{subscription.id}/transactions?limit=2", headers=member_headers)

    assert first.status_code == 200
    assert first.json()["count"] == 3
    assert len(first.json()["items"]) == 2

    second = await client.get(f"/api/subscriptions/{subscription.id}/transactions?limit=2&offset=2", headers=member_headers)

    assert len(second.json()["items"]) == 1
    assert {item["id"] for item in first.json()["items"]}.isdisjoint({item["id"] for item in second.json()["items"]})


async def test_a_plan_bills_by_a_unit_and_a_number_together_or_by_neither(client, tenant, admin_headers):
    """The page draws the sentence off the unit alone, so half a rule reads as `Every None Month` to every visitor."""
    payload = {"tenantId": tenant.id, "name": "Half a rule", "billingIntervalUnit": "month"}

    refused = await client.post("/api/plans", json=payload, headers=admin_headers)

    assert refused.status_code == 422
    assert refused.json()["code"] == "error.plan-billing-interval-incomplete"
    assert "billingIntervalValue" in refused.json()["errors"]

    without_a_unit = await client.post("/api/plans", json={**payload, "billingIntervalUnit": None, "billingIntervalValue": 3}, headers=admin_headers)

    assert without_a_unit.status_code == 422
    assert "billingIntervalUnit" in without_a_unit.json()["errors"]

    assert (await client.post("/api/plans", json={**payload, "billingIntervalValue": 1}, headers=admin_headers)).status_code == 201
    assert (await client.post("/api/plans", json={**payload, "name": "One off", "billingIntervalUnit": None}, headers=admin_headers)).status_code == 201
