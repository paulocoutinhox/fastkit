"""What somebody tries against the surfaces this application grew, written as the attempt and the answer."""

import pytest

from enums.user import UserRole, UserStatus
from helpers import cache, visitor
from helpers.security import create_token
from services.user import user_service
from tests.conftest import opened
from tests.factories import make_banner, make_content, make_gallery, make_gallery_photo, make_product, make_tenant

INJECTIONS = ["' OR '1'='1", "1; DROP TABLE banner", "%' OR '1'='1", "admin'--", "<script>alert(1)"]

DESTINATIONS = ["javascript:alert(1)", "JavaScript:alert(1)", "data:text/html,<script>alert(1)</script>", "vbscript:msgbox(1)", "//evil.test", "///evil.test", "/\\evil.test/x", "\\\\evil.test", "file:///etc/passwd"]


async def operating(db, tenant, **overrides):
    values = {"tenant_id": tenant.id if tenant else None, "username": "op", "email": "op@acme.com", "password": "secret123", "role": UserRole.ADMINISTRATOR, "status": UserStatus.ACTIVE} | overrides
    user = await user_service.create(db, values)
    await db.commit()

    return {"Authorization": f"Bearer {create_token(user.token, user.role, user.session_epoch)}"}


@pytest.fixture
async def caching(monkeypatch):
    monkeypatch.setattr(cache.settings.cache, "enabled", True)

    yield

    for space in cache.every():
        await space.clear()


@pytest.mark.parametrize("destination", DESTINATIONS)
async def test_a_banner_never_carries_a_destination_a_browser_would_run(client, admin_headers, destination):
    """A banner is drawn into the href of the public home, so an editor writing one of these would run script in every visitor."""
    answer = await client.post("/api/banners", json={"title": "Promo", "url": destination}, headers=admin_headers)

    assert answer.status_code == 422
    assert "url" in answer.json()["errors"]


async def test_a_banner_carries_the_destinations_a_link_is_for(client, admin_headers):
    for destination in ("https://example.com/promo", "/products/handbook", "/"):
        answer = await client.post("/api/banners", json={"title": "Promo", "url": destination}, headers=admin_headers)

        assert answer.status_code == 201, destination


@pytest.mark.parametrize("attempt", INJECTIONS)
async def test_a_uuid_carrying_an_injection_names_no_banner(client, db, tenant, tenant_headers, attempt):
    await make_banner(db, tenant)

    counted = await client.post(f"/api/banners/{attempt}/view", json={}, headers=tenant_headers)
    listed = await client.get("/api/banners/active", headers=tenant_headers)

    # The banner is still there, which is what says the term reached the database as a value and never as syntax.
    assert counted.status_code == 404
    assert len(listed.json()["items"]) == 1


async def test_a_name_nobody_signed_counts_nothing(client, db, tenant, tenant_headers):
    """Only this side signs a name, so a forged one is a reader nobody may be counted as."""
    banner = await make_banner(db, tenant)

    for forged in ("not-signed", "a.b", visitor.minted()[:-4] + "0000"):
        await client.post(f"/api/banners/{banner.uuid}/view", json={"visitor": forged}, headers=tenant_headers)

    await db.refresh(banner)

    assert banner.views == 0


async def test_one_brand_never_reads_what_another_assembled(caching, client, db, tenant, tenant_headers):
    """The key names the brand, so a page kept for one is never handed to the next one asking."""
    other = await make_tenant(db, code="rival", domain="rival.acme.com")

    await make_product(db, tenant, name="Mine")
    await make_product(db, other, name="Theirs")

    mine = await client.get("/api/commerce/products", headers=tenant_headers)
    theirs = await client.get("/api/commerce/products", headers={"X-Tenant-Code": other.code})

    assert [item["name"] for item in mine.json()["items"]] == ["Mine"]
    assert [item["name"] for item in theirs.json()["items"]] == ["Theirs"]


def test_a_search_term_never_collides_with_the_key_of_another_brand():
    """The parts are digested, so a term written to look like the rest of a key is still only a term."""
    honest = cache.named(surface="site", tenant=2, language="en")
    crafted = cache.named(surface="site", tenant=1, language="en", search='","tenant":2')

    assert honest != crafted
    assert cache.named(surface="site", tenant=1, search="a|b") != cache.named(surface="site", tenant=1, search="a", extra="b")


async def test_a_confined_operator_widens_nothing_with_a_filter(client, db, tenant):
    """A filter narrows a listing that is already narrowed, and naming another brand in it answers nothing."""
    other = await make_tenant(db, code="rival", domain="rival.acme.com")

    await make_content(db, tenant, title="Mine", tag="mine")
    await make_content(db, other, title="Theirs", tag="theirs")

    headers = await operating(db, tenant, username="strict", email="strict@acme.com")
    answer = await client.get(f"/api/contents?tenantId={other.id}", headers=headers)

    assert answer.json()["items"] == []


async def test_a_confined_operator_reaches_no_child_of_another_brand_through_its_parent(client, db, tenant):
    """A photo carries no brand of its own, so asking for the ones of another brand's gallery is where a leak would open."""
    other = await make_tenant(db, code="rival", domain="rival.acme.com")
    theirs = await make_gallery(db, other, tag="theirs")

    await make_gallery_photo(db, theirs, caption="Theirs")

    headers = await operating(db, tenant, username="strict", email="strict@acme.com")
    answer = await client.get(f"/api/gallery-photos?galleryId={theirs.id}", headers=headers)

    assert answer.json()["items"] == []


async def test_the_name_a_reader_is_counted_by_never_reaches_a_script(site):
    """It lives in a cookie the page cannot read, because a name a script can take is a reader a script can impersonate."""
    token = await opened(site, "/cookies")
    answer = await site.post("/cookies", data={"csrf_token": token, "action": "accept", "next": "/"}, follow_redirects=False)

    written = [value for name, value in answer.headers.multi_items() if name.lower() == "set-cookie" and value.startswith("fastkit_visitor=")]

    assert written
    assert all("httponly" in value.lower() for value in written)


async def test_a_banner_a_reader_may_not_see_is_a_banner_they_may_not_count(client, db, tenant, tenant_headers):
    """Counting one names it, so a uuid from another brand has to answer the same nothing the listing answers."""
    other = await make_tenant(db, code="rival", domain="rival.acme.com")
    theirs = await make_banner(db, other, title="Theirs")

    answer = await client.post(f"/api/banners/{theirs.uuid}/view", json={"visitor": visitor.minted()}, headers=tenant_headers)

    await db.refresh(theirs)

    assert answer.status_code == 404
    assert theirs.views == 0


async def test_the_markup_of_a_banner_is_drawn_and_never_run(site, db, tenant):
    """A title is written by an operator and read by every visitor, so what it carries is text wherever it lands."""
    await make_banner(db, tenant, title="<script>alert(1)</script>", url="https://example.com")

    page = await site.get("/")

    assert "<script>alert(1)</script>" not in page.text
    assert "&lt;script&gt;" in page.text
