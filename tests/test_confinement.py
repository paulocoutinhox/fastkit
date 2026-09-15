"""An operator that belongs to a brand is answered that brand, and what they write is written into it."""

import pytest

from enums.user import UserRole, UserStatus
from helpers.router import RESOURCES
from helpers.security import create_token
from models.user import User
from services.user import user_service
from tests.factories import make_content, make_content_category, make_currency, make_gallery, make_gallery_photo, make_plan, make_subscription, make_tenant


async def operating(db, tenant, **overrides):
    values = {"tenant_id": tenant.id if tenant else None, "username": "op", "email": "op@acme.com", "password": "secret123", "role": UserRole.ADMINISTRATOR, "status": UserStatus.ACTIVE} | overrides
    user = await user_service.create(db, values)
    await db.commit()

    return {"Authorization": f"Bearer {create_token(user.token, user.role, user.session_epoch)}"}


def test_every_resource_knows_how_it_is_confined():
    """A resource with no tenant, no parent to reach one through and no reason to be a catalogue would answer every brand to everybody."""
    lost = [name for name, service in RESOURCES.items() if "tenant_id" not in service.model.__table__.columns and service.reaches_through is None and not service.system_wide]

    assert len(RESOURCES) > 25, "the guard read too few resources to claim anything"
    assert lost == [], f"these have no way of being confined: {lost}"


async def test_a_confined_operator_is_answered_their_brand_and_no_other(client, db, tenant):
    other = await make_tenant(db, code="rival", domain="rival.acme.com")

    await make_content(db, tenant, title="Mine", tag="mine")
    await make_content(db, other, title="Theirs", tag="theirs")
    await make_content(db, None, title="Everybody", tag="all")

    headers = await operating(db, tenant, username="strict", email="strict@acme.com")
    answer = await client.get("/api/contents", headers=headers)

    assert sorted(item["title"] for item in answer.json()["items"]) == ["Mine"]


async def test_the_account_an_administrator_widened_is_answered_the_shared_rows_too(client, db, tenant):
    await make_content(db, tenant, title="Mine", tag="mine")
    await make_content(db, None, title="Everybody", tag="all")

    headers = await operating(db, tenant, username="wide", email="wide@acme.com", reaches_shared=True)
    listed = await client.get("/api/contents", headers=headers)
    resolved = await client.get("/api/contents/lookup", headers=headers)

    # The property is of the account and answers the listing and the lookup both.
    assert sorted(item["title"] for item in listed.json()["items"]) == ["Everybody", "Mine"]
    assert len(resolved.json()["items"]) == 2


async def test_an_operator_of_no_brand_is_answered_every_one_of_them(client, db, tenant):
    other = await make_tenant(db, code="rival", domain="rival.acme.com")

    await make_content(db, tenant, title="Mine", tag="mine")
    await make_content(db, other, title="Theirs", tag="theirs")

    headers = await operating(db, None, username="boss", email="boss@acme.com")
    answer = await client.get("/api/contents", headers=headers)

    assert sorted(item["title"] for item in answer.json()["items"]) == ["Mine", "Theirs"]


async def test_a_child_is_confined_by_the_row_it_belongs_to(client, db, tenant):
    """A photo carries no tenant of its own, so listing them directly is where a leak would open."""
    other = await make_tenant(db, code="rival", domain="rival.acme.com")

    mine = await make_gallery(db, tenant, tag="mine")
    theirs = await make_gallery(db, other, tag="theirs")

    await make_gallery_photo(db, mine, caption="Mine")
    await make_gallery_photo(db, theirs, caption="Theirs")

    headers = await operating(db, tenant, username="strict", email="strict@acme.com")
    answer = await client.get("/api/gallery-photos", headers=headers)

    assert [item["caption"] for item in answer.json()["items"]] == ["Mine"]


async def test_what_a_confined_operator_writes_is_written_into_their_brand(client, db, tenant):
    other = await make_tenant(db, code="rival", domain="rival.acme.com")
    headers = await operating(db, tenant, username="strict", email="strict@acme.com")

    made = await client.post("/api/contents", json={"title": "Mine", "tenantId": other.id}, headers=headers)

    # The payload naming another brand decides nothing, because the row is stamped and never asked about.
    assert made.status_code == 201
    assert made.json()["tenantId"] == tenant.id


@pytest.mark.parametrize("method", ["get", "put", "delete"])
async def test_a_row_of_another_brand_does_not_exist_for_a_confined_operator(client, db, tenant, method):
    other = await make_tenant(db, code="rival", domain="rival.acme.com")
    theirs = await make_content(db, other, title="Theirs", tag="theirs")

    headers = await operating(db, tenant, username="strict", email="strict@acme.com")
    call = getattr(client, method)
    answer = await (call(f"/api/contents/{theirs.id}", json={"title": "Stolen"}, headers=headers) if method == "put" else call(f"/api/contents/{theirs.id}", headers=headers))

    assert answer.status_code == 404


async def test_a_catalogue_of_the_system_is_reached_only_by_an_operator_of_no_brand(client, db, tenant):
    """A country belongs to no brand, so there is nothing to stamp and nothing to confine it by."""
    confined = await operating(db, tenant, username="strict", email="strict@acme.com")
    globally = await operating(db, None, username="boss", email="boss@acme.com")

    assert (await client.get("/api/countries", headers=confined)).status_code == 403
    assert (await client.get("/api/languages", headers=confined)).status_code == 403
    assert (await client.get("/api/tenants", headers=confined)).status_code == 403
    assert (await client.get("/api/countries", headers=globally)).status_code == 200


def test_every_resource_narrows_to_the_brand_of_whoever_asks():
    """Knowing how to be confined is not being confined, so the predicate is built for each of them and read."""
    confined = User(id=1, tenant_id=7, reaches_shared=False)
    widened = User(id=1, tenant_id=7, reaches_shared=True)
    globally = User(id=1, tenant_id=None, reaches_shared=False)
    read = 0

    for name, service in sorted(RESOURCES.items()):
        assert service.confinement(globally) is None, f"{name} narrows an operator that belongs to no brand"

        if service.system_wide:
            continue

        read += 1
        narrowed = str(service.confinement(confined))
        widened_by = str(service.confinement(widened))

        assert "tenant_id" in narrowed, f"{name} narrows by something that is not a tenant: {narrowed}"
        assert "7" in narrowed or ":" in narrowed, f"{name} narrows by no brand at all: {narrowed}"
        assert ("IS NULL" in widened_by) == service.shared, f"{name} answers the shared rows exactly when it is a catalogue: {widened_by}"

    assert read > 25, f"the guard built only {read} of them, so it is proving nothing"


async def test_the_panel_is_told_whether_the_account_belongs_to_a_brand(client, db, tenant):
    """A form that drew a tenant field with one option would be asking about something the server settles."""
    confined = await operating(db, tenant, username="strict", email="strict@acme.com")
    globally = await operating(db, None, username="boss", email="boss@acme.com")

    assert (await client.get("/api/meta/permissions", headers=confined)).json()["confined"] is True
    assert (await client.get("/api/meta/permissions", headers=globally)).json()["confined"] is False


async def test_the_panel_is_not_offered_a_catalogue_of_the_system_it_cannot_reach(client, db, tenant):
    confined = await operating(db, tenant, username="strict", email="strict@acme.com")
    globally = await operating(db, None, username="boss", email="boss@acme.com")

    reachable = (await client.get("/api/meta/permissions", headers=confined)).json()["resources"]
    everything = (await client.get("/api/meta/permissions", headers=globally)).json()["resources"]

    # Drawing a menu entry that answers 403 is worse than not drawing it.
    assert "countries" not in reachable
    assert "tenants" not in reachable
    assert {"countries", "languages", "tenants"} <= set(everything)


async def test_a_key_pointing_into_another_brand_is_refused(client, db, tenant):
    """The lookup would never have offered it, and the screen filtering and the service refusing are the two halves of one rule."""
    other = await make_tenant(db, code="rival", domain="rival.acme.com")
    theirs = await make_gallery(db, other, tag="theirs")
    mine = await make_gallery(db, tenant, tag="mine")

    headers = await operating(db, tenant, username="strict", email="strict@acme.com")
    image = {"image": "images/gallery/2026/01/01/a.webp"}

    planted = await client.post("/api/gallery-photos", json={"galleryId": theirs.id, "caption": "Planted"} | image, headers=headers)
    allowed = await client.post("/api/gallery-photos", json={"galleryId": mine.id, "caption": "Mine"} | image, headers=headers)

    assert planted.status_code == 422
    assert planted.json()["errors"] == {"galleryId": "The related record was not found."}
    assert allowed.status_code == 201


async def test_a_row_is_not_moved_into_another_brand_by_an_edit(client, db, tenant):
    other = await make_tenant(db, code="rival", domain="rival.acme.com")
    theirs = await make_gallery(db, other, tag="theirs")
    mine = await make_gallery(db, tenant, tag="mine")
    photo = await make_gallery_photo(db, mine, caption="Mine")

    headers = await operating(db, tenant, username="strict", email="strict@acme.com")
    moved = await client.put(f"/api/gallery-photos/{photo.id}", json={"galleryId": theirs.id}, headers=headers)

    assert moved.status_code == 422


async def test_an_operator_of_no_brand_points_a_key_wherever_it_belongs(client, db, tenant):
    other = await make_tenant(db, code="rival", domain="rival.acme.com")
    theirs = await make_gallery(db, other, tag="theirs")

    headers = await operating(db, None, username="boss", email="boss@acme.com")
    made = await client.post("/api/gallery-photos", json={"galleryId": theirs.id, "caption": "Any", "image": "images/gallery/2026/01/01/a.webp"}, headers=headers)

    assert made.status_code == 201


def test_a_catalogue_of_the_system_is_refused_whole_and_never_narrowed():
    """Narrowing one would ask what belongs to no brand which brand it belongs to, and the answer would be a crash."""
    from services.tenant import tenant_service

    assert tenant_service.confinement(User(id=1, tenant_id=7, reaches_shared=False)) is None


def test_every_service_is_found_by_the_walk_that_resolves_a_reference():
    """One level of subclasses misses a resource that gained a base of its own, and a key it points with would stop being checked."""
    from services.crud import services_by_model

    assert len(services_by_model()) >= len(RESOURCES)


@pytest.mark.parametrize("method", ["put", "delete"])
async def test_a_shared_row_is_read_by_a_widened_operator_and_never_written(client, db, tenant, method):
    """Rewriting a row every brand reads would let one brand decide what the others show."""
    shared = await make_content(db, None, title="Everybody", tag="all")

    headers = await operating(db, tenant, username="wide", email="wide@acme.com", reaches_shared=True)
    call = getattr(client, method)
    answer = await (call(f"/api/contents/{shared.id}", json={"title": "Rewritten"}, headers=headers) if method == "put" else call(f"/api/contents/{shared.id}", headers=headers))

    assert (await client.get(f"/api/contents/{shared.id}", headers=headers)).status_code == 200
    assert answer.status_code == 404


async def test_a_widened_operator_does_not_hang_a_child_on_a_shared_row(client, db, tenant):
    """A photo added to a shared gallery would appear on the site of every brand."""
    shared = await make_gallery(db, None, tag="shared")

    headers = await operating(db, tenant, username="wide", email="wide@acme.com", reaches_shared=True)
    planted = await client.post("/api/gallery-photos", json={"galleryId": shared.id, "caption": "Planted", "image": "images/gallery/2026/01/01/a.webp"}, headers=headers)

    assert planted.status_code == 422
    assert planted.json()["errors"] == {"galleryId": "The related record was not found."}


async def test_a_confined_operator_moves_no_balance_of_another_brand(client, db, tenant):
    other = await make_tenant(db, code="rival", domain="rival.acme.com")
    stranger = await user_service.create(db, {"tenant_id": other.id, "username": "stranger", "password": "secret123"})
    mine = await user_service.create(db, {"tenant_id": tenant.id, "username": "mine", "password": "secret123"})
    ours = await make_currency(db, tenant)
    theirs = await make_currency(db, other)

    headers = await operating(db, tenant, username="strict", email="strict@acme.com")
    entry = {"type": "credit", "amount": "10"}

    across = await client.post("/api/credit-transactions", json=entry | {"userId": stranger.id, "currencyId": ours.id}, headers=headers)
    foreign = await client.post("/api/credit-transactions", json=entry | {"userId": mine.id, "currencyId": theirs.id}, headers=headers)
    allowed = await client.post("/api/credit-transactions", json=entry | {"userId": mine.id, "currencyId": ours.id}, headers=headers)

    assert across.status_code == 422
    assert "userId" in across.json()["errors"]
    assert foreign.status_code == 422
    assert foreign.json()["errors"] == {"currencyId": "The related record was not found."}
    assert allowed.status_code == 201


async def test_a_confined_operator_does_not_deliver_a_subscription_of_another_brand(client, db, tenant):
    other = await make_tenant(db, code="rival", domain="rival.acme.com")
    stranger = await user_service.create(db, {"tenant_id": other.id, "username": "stranger", "password": "secret123"})
    subscription = await make_subscription(db, other, stranger, await make_plan(db, other))

    headers = await operating(db, tenant, username="strict", email="strict@acme.com")

    assert (await client.post(f"/api/subscriptions/{subscription.id}/activate", headers=headers)).status_code == 404
    assert (await client.post(f"/api/subscriptions/{subscription.id}/new-cycle", headers=headers)).status_code == 404


async def test_a_category_tag_is_unique_inside_a_brand_and_not_across_them(client, db, tenant, admin_headers):
    other = await make_tenant(db, code="rival", domain="rival.acme.com")
    await make_content_category(db, tenant_id=other.id, tag="legal")

    mine = await client.post("/api/content-categories", json={"name": "Legal", "tag": "legal", "tenantId": tenant.id}, headers=admin_headers)
    again = await client.post("/api/content-categories", json={"name": "Legal", "tag": "legal", "tenantId": tenant.id}, headers=admin_headers)

    assert mine.status_code == 201
    assert again.status_code == 409
    assert again.json()["code"] == "error.tag-already-used"


@pytest.mark.parametrize(
    ("path", "payload", "field"), [("/api/contents", {"title": "Mine", "categoryId": 999999}, "categoryId"), ("/api/external-products", {"integrationId": 999999, "planId": 999999, "externalId": "x"}, "integrationId"), ("/api/plan-entitlements", {"planId": 999999, "entitlementId": 999999}, "planId")]
)
async def test_a_key_naming_no_row_is_refused_by_name_for_an_operator_of_every_brand(client, admin_headers, path, payload, field):
    """Left to the flush it read as a duplicate, and a hook reading the parent met nothing and answered 500."""
    answer = await client.post(path, json=payload, headers=admin_headers)

    assert answer.status_code == 422
    assert answer.json()["code"] == "error.related-not-found"
    assert field in answer.json()["errors"]


async def test_an_edit_naming_another_brand_is_checked_against_the_brand_it_writes(client, db, tenant):
    """The payload's tenant is ignored on an edit as it is on a creation, so a rename is never refused for the brand nobody asked for."""
    other = await make_tenant(db, code="rival", domain="rival.acme.com")
    gems = await make_currency(db, tenant, code="gem")
    headers = await operating(db, tenant, username="renamer", email="renamer@acme.com")

    created = await client.post("/api/products", json={"name": "Pack", "currency": "USD", "price": "9.90", "credits": 10, "creditsCurrencyId": gems.id}, headers=headers)
    renamed = await client.put(f"/api/products/{created.json()['id']}", json={"name": "Renamed", "tenantId": other.id}, headers=headers)

    assert renamed.status_code == 200
    assert (renamed.json()["name"], renamed.json()["tenantId"]) == ("Renamed", tenant.id)


async def test_a_page_never_files_itself_under_a_category_of_another_brand(client, db, tenant, admin_headers):
    other = await make_tenant(db, code="rival", domain="rival.acme.com")
    theirs = await make_content_category(db, tenant_id=other.id)

    answer = await client.post("/api/contents", json={"title": "Mine", "tenantId": tenant.id, "categoryId": theirs.id}, headers=admin_headers)

    assert (answer.status_code, answer.json()["code"]) == (422, "error.related-not-found")


async def test_a_row_moves_into_one_brand_only_once_nothing_points_at_it(client, db, tenant, admin_headers):
    """Moving a currency another brand's product grants credits in would leave that product pointing across brands."""
    from tests.factories import make_product

    other = await make_tenant(db, code="rival", domain="rival.acme.com")
    gems = await make_currency(db, tenant)
    spare = await make_currency(db, tenant)
    await make_product(db, tenant, credits=10, credits_currency_id=gems.id)

    held = await client.put(f"/api/currencies/{gems.id}", json={"tenantId": other.id}, headers=admin_headers)
    free = await client.put(f"/api/currencies/{spare.id}", json={"tenantId": other.id}, headers=admin_headers)
    shared = await client.put(f"/api/currencies/{gems.id}", json={"tenantId": None}, headers=admin_headers)

    assert (held.status_code, held.json()["code"]) == (422, "error.record-still-referenced")
    assert free.status_code == 200
    assert shared.status_code == 200, "widening a row to every brand takes nothing from anybody"


async def test_a_row_is_shared_only_once_nothing_it_holds_points_into_one_brand(client, db, tenant, admin_headers):
    """A plan shared with every brand carries the entitlements it lists, so one of a single brand would be offered to all of them."""
    from tests.factories import make_entitlement, make_plan_entitlement

    plan = await make_plan(db, tenant)
    spare = await make_plan(db, tenant, code="yearly")
    await make_plan_entitlement(db, plan, await make_entitlement(db, tenant))
    await make_plan_entitlement(db, spare, await make_entitlement(db, None, code="everybody"))

    held = await client.put(f"/api/plans/{plan.id}", json={"tenantId": None}, headers=admin_headers)
    free = await client.put(f"/api/plans/{spare.id}", json={"tenantId": None}, headers=admin_headers)

    assert (held.status_code, held.json()["code"]) == (422, "error.children-of-a-brand")
    assert free.status_code == 200


async def test_the_shared_rows_a_widened_operator_reads_are_catalogues_and_never_accounts(client, db, tenant):
    """An account of no brand is an operator of the whole instance, and reaching the shared catalogue is no reason to read who runs it."""
    await operating(db, None, username="boss", email="boss@acme.com")
    headers = await operating(db, tenant, username="wide", email="wide@acme.com", reaches_shared=True)

    answer = await client.get("/api/users", headers=headers)

    assert [item["username"] for item in answer.json()["items"]] == ["wide"]
    assert (await client.get("/api/users/lookup", headers=headers)).json()["items"] == [{"id": answer.json()["items"][0]["id"], "label": "wide"}]


def test_a_child_shares_its_unbranded_rows_exactly_when_its_parent_does():
    """A child is confined by its parent, so declaring otherwise would read a shared parent's children as private or a private parent's children as shared."""
    from services.crud import services_by_model

    served = services_by_model()
    children = [service for service in served.values() if service.reaches_through is not None]

    assert len(children) > 8, "the guard read too few children to claim anything"
    assert [type(child).__name__ for child in children if child.shared != served[child.reaches_through.parent].shared] == []


async def test_an_operator_of_a_brand_never_grants_the_shared_rows_not_even_to_itself(client, db, tenant):
    headers = await operating(db, tenant, username="strict", email="strict@acme.com")
    own = (await client.get("/api/users", headers=headers)).json()["items"][0]

    edited = await client.put(f"/api/users/{own['id']}", json={"reachesShared": True}, headers=headers)
    created = await client.post("/api/users", json={"username": "fresh", "email": "fresh@acme.com", "password": "s3cret-password", "reachesShared": True}, headers=headers)

    assert edited.status_code == 200 and edited.json()["reachesShared"] is False
    assert created.status_code == 201 and created.json()["reachesShared"] is False


async def test_an_operator_of_a_brand_saves_its_own_row_that_points_at_a_shared_one(client, db, tenant):
    """A key the edit leaves as it was is not the operator's choice, so a brand's page an operator of no brand filed under a shared category is still the brand's to fix."""
    shared = await make_content_category(db, name="Shared", tag="shared")
    page = await make_content(db, tenant, title="Ours", tag="ours", category_id=shared.id)
    headers = await operating(db, tenant, username="strict", email="strict@acme.com")

    kept = await client.put(f"/api/contents/{page.id}", json={"title": "Ours, fixed", "categoryId": shared.id}, headers=headers)
    other = await make_content_category(db, name="Also Shared", tag="also-shared")
    moved = await client.put(f"/api/contents/{page.id}", json={"categoryId": other.id}, headers=headers)

    assert kept.status_code == 200
    assert (moved.status_code, moved.json()["code"]) == (422, "error.related-not-found")
