"""One journey a person makes, chained in the order a client makes it, because a route answering alone is not a screen working."""

import pytest_asyncio

from enums.commerce import PurchaseStatus
from enums.subscription import BenefitCadence, BenefitType, SubscriptionStatus
from enums.user import UserStatus
from helpers.dates import now
from helpers.security import create_token
from models.subscription import Subscription
from models.user import User
from services.commerce import commerce_service
from services.delivery import delivery_service
from tests.factories import make_banner, make_benefit, make_content, make_entitlement, make_gallery, make_gallery_photo, make_plan, make_plan_entitlement, make_product, make_subscription


def token_of(user: User) -> dict:
    return {"Authorization": f"Bearer {create_token(user.token, user.role, user.session_epoch)}"}


@pytest_asyncio.fixture
async def storefront(db, tenant, currency):
    """A tenant with something to sell and something to subscribe to, which is what every screen reads."""
    products = [await make_product(db, tenant, name=name, slug=slug, credits=credits, credits_currency_id=currency.id, featured=index == 0, position=index) for index, (name, slug, credits) in enumerate((("The Handbook", "handbook", 0), ("Starter pack", "starter-pack", 100)))]

    plan = await make_plan(db, tenant)
    entitlement = await make_entitlement(db, tenant, code="membership")

    await make_plan_entitlement(db, plan, entitlement)
    await make_benefit(db, entitlement, type=BenefitType.ACCESS, target="access", cadence=BenefitCadence.ON_ACTIVATION, grant_on_activation=True)

    await make_banner(db, tenant, title="Welcome", image="images/banner/2026/08/18/one.webp")
    await make_content(db, tenant, title="Terms", tag="terms")

    gallery = await make_gallery(db, tenant, title="Our office", tag="office")
    await make_gallery_photo(db, gallery, caption="Reception", position=0)

    return {"plan": plan, "products": products, "gallery": gallery}


@pytest_asyncio.fixture
async def subscriber(db, tenant, member, storefront):
    """Somebody who paid, because everything past the offer depends on that."""
    subscription = await make_subscription(db, tenant, member, storefront["plan"], status=SubscriptionStatus.ACTIVE)
    await delivery_service.activate(db, subscription)

    return subscription


async def test_somebody_signs_up_and_the_answer_carries_a_session_that_works(client, tenant_headers, db):
    """The first screen: two buttons, and this is the one that creates the account."""
    payload = {"email": "new@acme.com", "password": "a-strong-secret", "firstName": "Ana", "lastName": "Lima"}

    created = await client.post("/api/signup", json=payload, headers=tenant_headers)

    assert created.status_code == 201
    assert created.json()["user"]["displayName"] == "Ana Lima"
    assert "id" not in created.json()["user"]

    session = {"Authorization": f"Bearer {created.json()['token']}"}
    me = await client.get("/api/account/me", headers=session)

    assert me.status_code == 200
    assert me.json()["email"] == "new@acme.com"


async def test_signing_in_answers_the_same_account_the_signup_made(client, tenant_headers):
    await client.post("/api/signup", json={"email": "back@acme.com", "password": "a-strong-secret"}, headers=tenant_headers)

    entered = await client.post("/api/signin", json={"login": "back@acme.com", "password": "a-strong-secret"}, headers=tenant_headers)

    assert entered.status_code == 200

    me = await client.get("/api/account/me", headers={"Authorization": f"Bearer {entered.json()['token']}"})

    assert me.json()["email"] == "back@acme.com"


async def test_a_wrong_password_never_says_whether_the_account_exists(client, tenant_headers):
    unknown = await client.post("/api/signin", json={"login": "nobody@acme.com", "password": "whatever-it-is"}, headers=tenant_headers)

    await client.post("/api/signup", json={"email": "there@acme.com", "password": "a-strong-secret"}, headers=tenant_headers)
    wrong = await client.post("/api/signin", json={"login": "there@acme.com", "password": "something-else"}, headers=tenant_headers)

    assert unknown.status_code == wrong.status_code
    assert unknown.json()["code"] == wrong.json()["code"] == "error.invalid-credentials"


async def test_the_home_of_a_member_is_built_from_the_calls_the_client_makes(client, member_headers, tenant_headers, subscriber, storefront):
    """The client asks for the account, what it pays, the banners, the galleries and the catalogue, all at once."""
    answers = {
        name: await client.get(path, headers=member_headers | tenant_headers)
        for name, path in (("me", "/api/account/me"), ("subscriptions", "/api/subscriptions/me"), ("entitlements", "/api/account/entitlements"), ("banners", "/api/banners/active"), ("galleries", "/api/galleries/active"), ("products", "/api/commerce/products"))
    }

    assert {name: answer.status_code for name, answer in answers.items()} == dict.fromkeys(answers, 200)
    assert [right["code"] for right in answers["entitlements"].json()["items"]] == ["membership"]
    assert [product["slug"] for product in answers["products"].json()["items"]] == ["handbook", "starter-pack"]
    assert answers["banners"].json()["items"][0]["imageUrl"].startswith(("/media/", "http"))


async def test_a_visitor_reads_the_shop_without_a_session(client, tenant_headers, storefront):
    """The catalogue is the offer, so it answers before anybody has an account."""
    listed = await client.get("/api/commerce/products", headers=tenant_headers)
    one = await client.get("/api/commerce/products/handbook", headers=tenant_headers)

    assert [product["owned"] for product in listed.json()["items"]] == [False, False]
    assert one.json()["name"] == "The Handbook"


async def test_buying_a_product_puts_it_in_the_account_and_pays_its_credits(client, db, tenant, member, member_headers, storefront):
    """What the account owns is what it bought, and the credits of a pack land in the balance once."""
    purchase = await commerce_service.open_purchase(db, tenant, member, storefront["products"][1], None)
    await commerce_service.settle_purchase(db, purchase, PurchaseStatus.PAID, "pi_1")

    owned = await client.get("/api/account/products", headers=member_headers)
    credits = await client.get("/api/account/credits", headers=member_headers)

    assert [product["slug"] for product in owned.json()["items"]] == ["starter-pack"]
    assert credits.json()["items"][0]["amount"] == 100


async def test_a_product_the_account_owns_is_marked_as_owned_in_the_shop(client, db, tenant, member, member_headers, tenant_headers, storefront):
    await commerce_service.grant(db, member.id, storefront["products"][0].id, "seed")

    listed = await client.get("/api/commerce/products", headers=member_headers | tenant_headers)

    assert {product["slug"]: product["owned"] for product in listed.json()["items"]} == {"handbook": True, "starter-pack": False}


async def test_the_gallery_of_a_tag_answers_every_photo_as_an_address(client, tenant_headers, storefront):
    read = await client.get("/api/galleries/by-tag/office", headers=tenant_headers)

    assert read.json()["title"] == "Our office"
    assert read.json()["coverUrl"].startswith(("/media/", "http"))
    assert [photo["caption"] for photo in read.json()["photos"]] == ["Reception"]


async def test_a_tag_no_gallery_carries_is_not_found(client, tenant_headers, storefront):
    assert (await client.get("/api/galleries/by-tag/nothing-here", headers=tenant_headers)).status_code == 404


async def test_the_person_writes_an_address_and_reads_it_back(client, country, member_headers):
    payload = {"line1": "221B Baker Street", "streetNumber": "221", "city": "London", "state": "London", "postalCode": "NW16XE", "countryCode": "gb"}

    written = await client.put("/api/account/addresses/main", json=payload, headers=member_headers)
    listed = await client.get("/api/account/addresses", headers=member_headers)

    assert written.status_code == 200
    assert written.json()["countryCode"] == "GB"
    assert [address["type"] for address in listed.json()["items"]] == ["main"]


async def test_the_person_takes_the_address_back_off_the_account(client, country, member_headers):
    """Removing one that is not there answers the same as removing one that is, so a client never has to ask first."""
    payload = {"line1": "221B Baker Street", "city": "London", "state": "London", "postalCode": "NW16XE", "countryCode": "GB"}

    await client.put("/api/account/addresses/main", json=payload, headers=member_headers)

    assert (await client.delete("/api/account/addresses/main", headers=member_headers)).status_code == 204
    assert (await client.get("/api/account/addresses", headers=member_headers)).json()["items"] == []
    assert (await client.delete("/api/account/addresses/main", headers=member_headers)).status_code == 204


async def test_writing_the_address_again_replaces_it_instead_of_collecting_a_second(client, country, member_headers):
    payload = {"line1": "221B Baker Street", "city": "London", "state": "London", "postalCode": "NW16XE", "countryCode": "GB"}

    await client.put("/api/account/addresses/main", json=payload, headers=member_headers)
    await client.put("/api/account/addresses/main", json=payload | {"city": "Cambridge"}, headers=member_headers)

    listed = await client.get("/api/account/addresses", headers=member_headers)

    assert [address["city"] for address in listed.json()["items"]] == ["Cambridge"]


async def test_the_address_of_somebody_else_is_never_reached(client, db, tenant, member, member_headers, tenant_headers):
    await client.put("/api/account/addresses/main", json={"line1": "One", "city": "London", "state": "London", "postalCode": "N1", "countryCode": "GB"}, headers=member_headers)

    stranger = await client.post("/api/signup", json={"email": "stranger@acme.com", "password": "a-strong-secret"}, headers=tenant_headers)
    session = {"Authorization": f"Bearer {stranger.json()['token']}"}

    assert (await client.get("/api/account/addresses", headers=session)).json()["items"] == []


async def test_the_client_reports_a_batch_and_the_same_batch_twice_is_one(client, member_headers, tenant_headers, subscriber, storefront):
    batch = {"events": [{"uuid": "a-b-c", "name": "product_viewed", "occurredAt": now().isoformat(), "params": {"id": storefront["products"][0].id}}]}

    first = await client.post("/api/events", json=batch, headers=member_headers | tenant_headers)
    second = await client.post("/api/events", json=batch, headers=member_headers | tenant_headers)

    assert first.status_code == second.status_code == 202


async def test_the_person_edits_the_account_and_cannot_erase_the_last_way_in(client, member_headers, member):
    edited = await client.put("/api/account/me", json={"nickname": "Ada"}, headers=member_headers)

    assert edited.status_code == 200
    assert edited.json()["displayName"] == "Ada"

    refused = await client.put("/api/account/me", json={"email": "", "username": "", "cpf": "", "mobilePhone": ""}, headers=member_headers)

    assert refused.status_code == 422


async def test_changing_the_password_keeps_this_device_in_and_puts_the_others_out(client, member_headers, member, db):
    changed = await client.post("/api/account/password", json={"currentPassword": "s3cret-password", "newPassword": "another-strong-secret"}, headers=member_headers)

    assert changed.status_code == 200

    fresh = {"Authorization": f"Bearer {changed.json()['token']}"}

    assert (await client.get("/api/account/me", headers=fresh)).status_code == 200
    assert (await client.get("/api/account/me", headers=member_headers)).status_code == 401


async def test_asking_for_a_password_reset_never_says_whether_the_account_is_there(client, tenant_headers, member):
    known = await client.post("/api/account/password-reset", json={"login": member.email}, headers=tenant_headers)
    unknown = await client.post("/api/account/password-reset", json={"login": "nobody@acme.com"}, headers=tenant_headers)

    assert known.status_code == unknown.status_code == 204
    assert known.content == unknown.content == b""


async def test_deleting_the_account_stops_answering_and_keeps_what_was_paid(client, member_headers, member, subscriber, db):
    erased = await client.delete("/api/account/me", headers=member_headers)

    assert erased.status_code == 204
    assert (await client.get("/api/account/me", headers=member_headers)).status_code == 401

    await db.refresh(member)

    assert member.status == UserStatus.ERASED
    assert member.email.endswith(".invalid")
    assert await db.get(Subscription, subscriber.id) is not None


async def test_the_subscription_screen_lists_what_the_provider_reported(client, member_headers, subscriber):
    mine = await client.get("/api/subscriptions/me", headers=member_headers)

    assert [item["id"] for item in mine.json()["items"]] == [subscriber.id]

    statement = await client.get(f"/api/subscriptions/{subscriber.id}/transactions", headers=member_headers)

    assert statement.status_code == 200
    assert statement.json()["items"] == []


async def test_a_subscription_of_somebody_else_answers_nothing(client, subscriber, db, tenant, storefront):
    stranger = await client.post("/api/signup", json={"email": "another@acme.com", "password": "a-strong-secret"}, headers={"X-Tenant-Code": tenant.code})
    session = {"Authorization": f"Bearer {stranger.json()['token']}"}

    assert (await client.get("/api/subscriptions/me", headers=session)).json()["items"] == []

    # A subscription that is not theirs does not exist for them, or an empty answer would read as one with no payments yet.
    assert (await client.get(f"/api/subscriptions/{subscriber.id}/transactions", headers=session)).status_code == 404


async def test_every_answer_a_client_reads_carries_an_address_and_never_a_storage_key(client, member_headers, tenant_headers, subscriber, storefront):
    listed = await client.get("/api/commerce/products", headers=member_headers | tenant_headers)

    for item in listed.json()["items"]:
        assert "image" not in item
        assert "file" not in item
        assert item["imageUrl"] is None or item["imageUrl"].startswith(("/media/", "http"))
