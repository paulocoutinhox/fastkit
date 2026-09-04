"""An operator that belongs to a brand is answered that brand, and what they write is written into it."""

import pytest

from enums.user import UserRole, UserStatus
from helpers.router import RESOURCES
from helpers.security import create_token
from models.user import User
from services.user import user_service
from tests.factories import make_content, make_gallery, make_gallery_photo, make_tenant


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
        assert "IS NULL" in widened_by, f"{name} does not answer the shared rows to an account that was given them: {widened_by}"

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
