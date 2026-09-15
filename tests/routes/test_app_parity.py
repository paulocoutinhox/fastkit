"""What a person does on the site, an application does through the API, because both are the same product."""

import pytest
from sqlalchemy import select

from enums.newsletter import NewsletterStatus
from models.email import OutboundEmail
from models.newsletter import NewsletterSubscription
from tests.factories import make_country, make_plan, make_product, make_purchase


async def test_an_application_lists_the_plans_a_tenant_sells(client, db, tenant, tenant_headers):
    """The paywall of an application is the same list the site draws, and it carries an address and never a storage key."""
    await make_plan(db, tenant, code="monthly", name="Monthly", image="images/plan/2026/08/19/a.webp")
    await make_plan(db, tenant, code="hidden", name="Hidden", active=False)

    answer = await client.get("/api/subscriptions/plans", headers=tenant_headers)
    items = answer.json()["items"]

    assert answer.status_code == 200
    assert [row["code"] for row in items] == ["monthly"]
    assert items[0]["imageUrl"].endswith("a.webp")
    assert "image" not in items[0]


async def test_an_application_lists_the_countries_an_address_may_name(client, db, tenant_headers):
    from enums.country import PostalCodeProvider

    await make_country(db)
    await make_country(db, name="Brazil", code_iso_3166_1="BR", postal_code_provider=PostalCodeProvider.VIACEP)
    await make_country(db, name="Nowhere", code_iso_3166_1="ZZ", active=False)

    items = (await client.get("/api/countries/offered", headers=tenant_headers)).json()["items"]

    assert [row["codeIso31661"] for row in items] == ["BR", "GB"]
    assert [row["postalCodeProvider"] for row in items] == ["viacep", None]


async def test_a_postal_code_is_answered_to_an_account_and_to_nobody_else(client, db, member_headers, tenant_headers, monkeypatch):
    from enums.country import PostalCodeProvider
    from helpers import postal_code
    from helpers.postal_code import PostalAddress

    await make_country(db, name="Brazil", code_iso_3166_1="BR", postal_code_provider=PostalCodeProvider.VIACEP)
    await make_country(db)

    async def found(provider, code):
        return PostalAddress(line1="Avenida Paulista", district="Bela Vista", city="São Paulo", state="SP")

    monkeypatch.setattr(postal_code, "find", found)

    assert (await client.get("/api/countries/BR/postal-code/01310100", headers=tenant_headers)).status_code == 401

    answer = await client.get("/api/countries/BR/postal-code/01310100", headers={**tenant_headers, **member_headers})

    assert answer.status_code == 200
    assert answer.json()["city"] == "São Paulo"

    # A country with nobody to ask is one this never asks about.
    assert (await client.get("/api/countries/GB/postal-code/NW16XE", headers={**tenant_headers, **member_headers})).status_code == 404


async def test_an_application_writes_to_the_operator(client, db, tenant, tenant_headers):
    answer = await client.post("/api/contact", json={"name": "Ada", "email": "ada@acme.com", "message": "I would like to know more about the plans."}, headers=tenant_headers)
    queued = await db.scalar(select(OutboundEmail).where(OutboundEmail.template == "contact"))

    assert answer.status_code == 204
    assert queued.reply_to == "ada@acme.com"


async def test_an_application_sends_a_token_google_minted_whole(client, tenant, tenant_headers, monkeypatch):
    """A reCAPTCHA token runs to a couple of thousand characters, and the contact and the newsletter of the API cut the answer at sixty four and refused every one."""
    from helpers import captcha

    async def passed(answer, token, remote_ip):
        return answer == "t" * 2000

    monkeypatch.setattr(captcha, "verify", passed)

    for path, payload in [("/api/contact", {"name": "Ada", "email": "ada@acme.com", "message": "I would like to know more about the plans."}), ("/api/newsletter", {"email": "ada@acme.com"})]:
        assert (await client.post(path, json=payload | {"captchaAnswer": "t" * 2000}, headers=tenant_headers)).status_code == 204, path


async def test_an_application_joins_and_leaves_the_newsletter(client, db, tenant, tenant_headers):
    assert (await client.post("/api/newsletter", json={"email": "ada@acme.com"}, headers=tenant_headers)).status_code == 204

    record = await db.scalar(select(NewsletterSubscription))

    assert record.status == NewsletterStatus.PENDING

    assert (await client.post(f"/api/newsletter/confirm/{record.token}", headers=tenant_headers)).status_code == 204
    await db.refresh(record)
    assert record.status == NewsletterStatus.CONFIRMED

    assert (await client.post(f"/api/newsletter/unsubscribe/{record.token}", headers=tenant_headers)).status_code == 204
    await db.refresh(record)
    assert record.status == NewsletterStatus.UNSUBSCRIBED

    assert (await client.post("/api/newsletter/confirm/nothing-here", headers=tenant_headers)).status_code == 404


async def test_an_application_opens_one_purchase_of_its_own_and_no_other(client, db, tenant, member, member_headers, tenant_headers):
    from services.user import user_service

    product = await make_product(db, tenant)
    mine = await make_purchase(db, tenant, member, product)

    stranger = await user_service.create(db, {"tenant_id": tenant.id, "username": "stranger", "password": "s3cret-password"})
    theirs = await make_purchase(db, tenant, stranger, product)

    headers = {**tenant_headers, **member_headers}

    assert (await client.get(f"/api/account/purchases/{mine.id}", headers=headers)).json()["reference"] == mine.reference
    assert (await client.get(f"/api/account/purchases/{theirs.id}", headers=headers)).status_code == 404


@pytest.mark.parametrize("path", ["/api/commerce/products/handbook/checkout", "/api/subscriptions/plans/monthly/checkout"])
async def test_a_checkout_names_where_the_gateway_sends_the_buyer_back_to(client, db, tenant, member_headers, tenant_headers, path):
    """An application knows its own way home, and a value that is not an address is refused before a gateway ever sees it."""
    await make_product(db, tenant, slug="handbook")
    await make_plan(db, tenant, code="monthly")

    headers = {**tenant_headers, **member_headers}
    refused = await client.post(path, json={"successUrl": "not-a-url", "cancelUrl": "https://app.acme.com/cancel"}, headers=headers)

    assert refused.status_code == 422
    assert "successUrl" in refused.json()["errors"]

    # A tenant with no gateway configured answers what that is, and never a stack trace.
    unavailable = await client.post(path, json={"successUrl": "https://app.acme.com/ok", "cancelUrl": "https://app.acme.com/cancel"}, headers=headers)

    assert unavailable.status_code == 400
    assert unavailable.json()["code"] == "error.checkout-unavailable"


@pytest.mark.parametrize("address", ["http://[", "https://[::1", "http://a]b", "https://acme.com:0/ok", "https://:8000/ok"])
async def test_a_return_address_no_parser_reads_is_refused_before_a_purchase_is_written(client, db, tenant, member_headers, tenant_headers, address):
    """A pattern reads a bracket left open as an address, and the checkout would write a purchase and then fail on it."""
    from models.commerce import Purchase

    await make_product(db, tenant, slug="handbook")

    answer = await client.post("/api/commerce/products/handbook/checkout", json={"successUrl": address, "cancelUrl": "https://app.acme.com/cancel"}, headers={**tenant_headers, **member_headers})

    assert answer.status_code == 422
    assert "successUrl" in answer.json()["errors"]
    assert await db.scalar(select(Purchase)) is None


@pytest.mark.parametrize("path", ["/api/commerce/products/nothing/checkout", "/api/subscriptions/plans/nothing/checkout"])
async def test_a_checkout_of_something_a_tenant_does_not_sell_is_not_a_checkout(client, member_headers, tenant_headers, path):
    answer = await client.post(path, json={"successUrl": "https://app.acme.com/ok", "cancelUrl": "https://app.acme.com/cancel"}, headers={**tenant_headers, **member_headers})

    assert answer.status_code == 404


@pytest.mark.parametrize("path", ["/api/commerce/products/handbook/checkout", "/api/subscriptions/plans/monthly/checkout"])
async def test_a_checkout_needs_an_account(client, db, tenant, tenant_headers, path):
    await make_product(db, tenant, slug="handbook")
    await make_plan(db, tenant, code="monthly")

    answer = await client.post(path, json={"successUrl": "https://app.acme.com/ok", "cancelUrl": "https://app.acme.com/cancel"}, headers=tenant_headers)

    assert answer.status_code == 401


async def test_a_postal_code_the_provider_does_not_know_is_not_an_address(client, db, member_headers, tenant_headers, monkeypatch):
    from enums.country import PostalCodeProvider
    from helpers import postal_code

    await make_country(db, name="Brazil", code_iso_3166_1="BR", postal_code_provider=PostalCodeProvider.VIACEP)

    async def missing(provider, code):
        return None

    monkeypatch.setattr(postal_code, "find", missing)

    answered = await client.get("/api/countries/BR/postal-code/00000000", headers={**tenant_headers, **member_headers})

    assert answered.status_code == 404
    assert answered.json()["code"] == "error.postal-code-not-found"


async def test_an_application_cannot_buy_what_the_account_already_owns(client, db, tenant, member, member_headers, tenant_headers):
    from enums.integration import Provider
    from helpers.security import encrypt
    from services.commerce import commerce_service
    from tests.factories import make_integration, make_product

    await make_integration(db, tenant, provider=Provider.STRIPE, stripe_api_key_encrypted=encrypt("sk_test_1"))
    product = await make_product(db, tenant, slug="handbook")
    await commerce_service.grant(db, member.id, product.id, "gift")

    answer = await client.post("/api/commerce/products/handbook/checkout", json={"successUrl": "https://app.acme.com/ok", "cancelUrl": "https://app.acme.com/no"}, headers={**tenant_headers, **member_headers})

    assert (answer.status_code, answer.json()["code"]) == (409, "error.product-already-owned")
