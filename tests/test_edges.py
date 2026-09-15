"""The branches nothing else walks, each one a thing that happens and would be silent if it broke."""

import pytest
from sqlalchemy import select

from enums.commerce import PurchaseStatus
from helpers import captcha, signing
from helpers.settings import settings
from models.commerce import Purchase, UserProduct
from services.commerce import commerce_service, product_service
from services.gallery import gallery_service
from services.gateway import signature_parts
from tests.factories import make_gallery, make_product


def test_a_value_carrying_no_signature_is_read_as_nothing():
    assert signing.unsign("flash", "no-dot-in-here") is None
    assert signing.unsign("flash", "") is None


def test_a_challenge_nobody_implemented_is_refused_where_it_is_built():
    """The base is a contract, so a provider that forgets half of it never reaches a form to fail in."""
    with pytest.raises(TypeError):
        type("Empty", (captcha.Captcha,), {})()


async def balance_of(db, user, currency) -> int:
    """What the account holds of one currency, read from the balance the ledger of that currency explains."""
    from services.account import user_balance_service

    held = await user_balance_service.list_for_user(db, user.id)

    return next((row.amount for row in held if row.currency_id == currency.id), 0)


def test_a_signature_header_carrying_junk_between_the_commas_is_read_past():
    moment, signatures = signature_parts("t=1,nonsense,v1=abc")

    assert moment == "1"
    assert signatures == ["abc"]


async def test_a_session_cookie_that_is_not_a_token_answers_nobody(site):
    site.cookies.set(settings.site.session_cookie, "not-a-jwt-at-all", domain="acme.test", path="/")

    answer = await site.get("/account", follow_redirects=False)

    assert answer.status_code == 303


async def test_a_flash_cookie_nobody_signed_is_read_as_no_message(site):
    site.cookies.set(settings.site.flash_cookie, "forged.by-somebody", domain="acme.test", path="/")

    answer = await site.get("/")

    assert answer.status_code == 200


async def test_the_account_removes_the_address_of_one_purpose(client, db, member, member_headers):
    payload = {"line1": "221B Baker Street", "city": "London", "state": "London", "postalCode": "NW16XE", "countryCode": "GB"}

    await client.put("/api/account/addresses/main", json=payload, headers=member_headers)

    removed = await client.delete("/api/account/addresses/main", headers=member_headers)

    assert removed.status_code == 204
    assert (await client.get("/api/account/addresses", headers=member_headers)).json()["items"] == []


async def test_removing_an_address_that_is_not_there_is_not_an_error(client, member_headers):
    assert (await client.delete("/api/account/addresses/billing", headers=member_headers)).status_code == 204


async def test_a_product_slug_naming_nothing_is_not_found(client, tenant_headers):
    assert (await client.get("/api/commerce/products/nothing-here", headers=tenant_headers)).status_code == 404


async def test_a_gallery_tag_naming_nothing_is_not_a_page(site, db, tenant):
    await make_gallery(db, tenant, tag="office")

    assert (await site.get("/gallery/nothing-here")).status_code == 404


async def test_a_sitemap_of_a_host_no_tenant_answers_for_is_not_a_page(app, monkeypatch):
    from httpx import ASGITransport, AsyncClient

    monkeypatch.setattr(settings.site, "default_tenant", "")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://nobody.test") as client:
        assert (await client.get("/sitemap.xml")).status_code == 404


async def test_a_recovery_the_rules_refuse_draws_the_form_again(site):
    from tests.conftest import opened

    token = await opened(site, "/account/password-recovery")

    assert (await site.post("/account/password-recovery", data={"csrf_token": token, "login": "x"})).status_code == 422


async def test_a_profile_the_rules_refuse_draws_the_form_again(signed_in):
    from tests.conftest import opened

    token = await opened(signed_in, "/account/profile")

    assert (await signed_in.post("/account/profile", data={"csrf_token": token, "username": "ab"})).status_code == 422


async def test_a_new_password_the_rules_refuse_draws_the_form_again(signed_in):
    from tests.conftest import opened

    token = await opened(signed_in, "/account/password")

    assert (await signed_in.post("/account/password", data={"csrf_token": token, "current_password": "s3cret-password", "new_password": "short"})).status_code == 422


async def test_a_gateway_with_no_key_cannot_open_a_checkout(db, tenant, member):
    from enums.integration import Provider
    from helpers.errors import AppError
    from services.checkout import checkout_service
    from tests.factories import make_integration

    integration = await make_integration(db, tenant, provider=Provider.STRIPE)

    with pytest.raises(AppError) as refused:
        await checkout_service.open_session(integration, {"mode": "payment"})

    assert refused.value.code == "error.checkout-unavailable"


async def test_a_gallery_is_given_the_tag_its_title_makes(db, tenant):
    gallery = await gallery_service.create(db, {"tenant_id": tenant.id, "title": "Our Office in London"})

    assert gallery.tag == "our-office-in-london"


async def test_a_currency_is_stored_the_way_a_gateway_reads_it(db, tenant):
    product = await product_service.create(db, {"tenant_id": tenant.id, "name": "Handbook", "currency": "usd"})

    assert product.currency == "USD"


async def test_a_payment_the_gateway_reports_twice_is_settled_once(db, tenant, member, currency):
    product = await make_product(db, tenant, credits=100, credits_currency_id=currency.id)
    purchase = await commerce_service.open_purchase(db, tenant, member, product, None)

    await commerce_service.settle_purchase(db, purchase, PurchaseStatus.PAID, "pi_1")
    await commerce_service.settle_purchase(db, purchase, PurchaseStatus.PAID, "pi_1")
    await db.refresh(member)

    assert await balance_of(db, member, currency) == 100
    assert len((await db.execute(select(UserProduct))).scalars().all()) == 1


async def test_a_payment_that_did_not_go_through_hands_nothing_over(db, tenant, member):
    product = await make_product(db, tenant)
    purchase = await commerce_service.open_purchase(db, tenant, member, product, None)

    await commerce_service.settle_purchase(db, purchase, PurchaseStatus.FAILED, "pi_2")
    await db.refresh(purchase)

    assert purchase.status == PurchaseStatus.FAILED
    assert purchase.paid_at is None
    assert await db.scalar(select(UserProduct)) is None


async def test_a_refund_marks_the_payment_and_never_reaches_for_what_it_bought(db, tenant, member):
    """What entered is the account's for good, so the money going back is a status and not a repossession."""
    product = await make_product(db, tenant)
    purchase = await commerce_service.open_purchase(db, tenant, member, product, None)

    await commerce_service.settle_purchase(db, purchase, PurchaseStatus.PAID, "pi_3")
    await commerce_service.settle_purchase(db, purchase, PurchaseStatus.REFUNDED)
    await db.refresh(purchase)

    assert purchase.status == PurchaseStatus.REFUNDED
    assert await db.scalar(select(UserProduct)) is not None


async def test_a_purchase_is_found_by_the_reference_this_side_minted(db, tenant, member):
    from services.commerce import purchase_service

    product = await make_product(db, tenant)
    purchase = await commerce_service.open_purchase(db, tenant, member, product, None)

    assert (await purchase_service.find_by_reference(db, purchase.reference)).id == purchase.id
    assert await purchase_service.find_by_reference(db, "nobody-minted-this") is None
    assert await db.scalar(select(Purchase)) is not None


async def test_a_machine_with_no_domain_of_its_own_serves_the_tenant_the_environment_names(client, tenant):
    """A developer machine answers on localhost, which is a host no tenant will ever carry."""
    answer = await client.get("/")

    assert answer.status_code == 200
    assert tenant.name in answer.text


async def test_the_products_a_benefit_may_hand_over_are_the_ones_its_entitlement_reaches(client, db, tenant, admin_headers):
    """The form asks the API to narrow the list, so an entitlement of one tenant never offers the product of another."""
    from tests.factories import make_entitlement, make_tenant

    entitlement = await make_entitlement(db, tenant)
    mine = await make_product(db, tenant, name="Mine")
    shared = await make_product(db, name="Shared")

    await make_product(db, await make_tenant(db, code="other", domain="other.test"), name="Theirs")

    listed = await client.get(f"/api/products/lookup?entitlementId={entitlement.id}", headers=admin_headers)

    assert sorted(item["id"] for item in listed.json()["items"]) == sorted([mine.id, shared.id])


async def test_the_plans_a_gateway_may_be_pointed_at_are_the_ones_of_its_own_tenant(client, db, tenant, admin_headers):
    from enums.integration import Provider
    from tests.factories import make_integration, make_plan, make_tenant

    integration = await make_integration(db, tenant, provider=Provider.STRIPE)
    mine = await make_plan(db, tenant, code="monthly")

    await make_plan(db, await make_tenant(db, code="other", domain="other.test"), code="theirs")

    listed = await client.get(f"/api/plans/lookup?integrationId={integration.id}", headers=admin_headers)

    assert [item["id"] for item in listed.json()["items"]] == [mine.id]


async def test_a_page_that_cannot_even_be_drawn_still_answers_something():
    """Whatever broke may be what the page needs, and a handler that raises leaves the visitor with no body at all."""
    from fastapi import FastAPI
    from httpx import ASGITransport, AsyncClient

    from helpers import errors

    async def unreachable(request):
        raise RuntimeError("the database the page needs is the thing that broke")

    application = FastAPI()
    errors.setup(application, None, unreachable)

    @application.get("/breaks")
    async def breaks():
        raise RuntimeError("something a bug would do")

    async with AsyncClient(transport=ASGITransport(app=application, raise_app_exceptions=False), base_url="http://probe.test") as visitor:
        answer = await visitor.get("/breaks")

    assert answer.status_code == 500
    assert answer.json()["code"] == "error.internal"
