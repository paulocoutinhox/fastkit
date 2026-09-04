from datetime import timedelta

from sqlalchemy import func, select

from enums.banner import BannerPlacement
from helpers import visitor
from helpers.dates import now
from models.banner import BannerImpression
from tests.factories import make_banner, make_language, make_tenant


async def test_create_refuses_an_inverted_window(client, admin_headers):
    payload = {"title": "Promo", "starts_at": "2026-03-01T00:00:00Z", "ends_at": "2026-02-01T00:00:00Z"}

    response = await client.post("/api/banners", json=payload, headers=admin_headers)

    assert response.status_code == 422
    assert response.json()["code"] == "error.availability-window-inverted"


async def test_create_accepts_an_open_window(client, admin_headers):
    response = await client.post("/api/banners", json={"title": "Promo"}, headers=admin_headers)

    assert response.status_code == 201


async def test_active_answers_what_is_live_right_now(client, db, tenant, tenant_headers):
    moment = now()

    await make_banner(db, tenant, title="Live", starts_at=moment - timedelta(days=1), ends_at=moment + timedelta(days=1))
    await make_banner(db, tenant, title="Over", starts_at=moment - timedelta(days=5), ends_at=moment - timedelta(days=2))
    await make_banner(db, tenant, title="Ahead", starts_at=moment + timedelta(days=2))
    await make_banner(db, tenant, title="Off", active=False)
    await make_banner(db, None, title="Shared")

    response = await client.get("/api/banners/active", headers=tenant_headers)

    assert response.status_code == 200
    assert sorted(item["title"] for item in response.json()["items"]) == ["Live", "Shared"]


async def test_active_orders_by_position(client, db, tenant, tenant_headers):
    await make_banner(db, tenant, title="Second", position=2)
    await make_banner(db, tenant, title="First", position=1)

    response = await client.get("/api/banners/active", headers=tenant_headers)

    assert [item["title"] for item in response.json()["items"]] == ["First", "Second"]


async def test_update_keeps_the_window_rule(client, db, tenant, admin_headers):
    banner = await make_banner(db, tenant, starts_at=now())

    response = await client.put(f"/api/banners/{banner.id}", json={"endsAt": "2020-01-01T00:00:00Z"}, headers=admin_headers)

    assert response.status_code == 422


async def test_active_answers_only_the_space_that_was_asked_for(client, db, tenant, tenant_headers):
    await make_banner(db, tenant, title="Na home", placement=BannerPlacement.HOME)
    await make_banner(db, tenant, title="No espaço um", placement=BannerPlacement.APP_SPACE1)
    await make_banner(db, tenant, title="No espaço dois", placement=BannerPlacement.APP_SPACE2)

    response = await client.get("/api/banners/active?placement=app_space1", headers=tenant_headers)

    assert [item["title"] for item in response.json()["items"]] == ["No espaço um"]


async def test_active_without_a_space_answers_every_one_of_them(client, db, tenant, tenant_headers):
    await make_banner(db, tenant, title="Na home", placement=BannerPlacement.HOME)
    await make_banner(db, tenant, title="No espaço um", placement=BannerPlacement.APP_SPACE1)

    response = await client.get("/api/banners/active", headers=tenant_headers)

    assert [item["title"] for item in response.json()["items"]] == ["Na home", "No espaço um"]


async def test_a_banner_lands_on_the_home_when_no_space_is_stated(client, admin_headers):
    response = await client.post("/api/banners", json={"title": "Promo"}, headers=admin_headers)

    assert response.status_code == 201
    assert response.json()["placement"] == BannerPlacement.HOME


async def test_a_banner_is_filtered_by_its_space_in_the_admin(client, db, tenant, admin_headers):
    await make_banner(db, tenant, title="Na home", placement=BannerPlacement.HOME)
    await make_banner(db, tenant, title="No espaço três", placement=BannerPlacement.APP_SPACE3)

    listed = (await client.get("/api/banners?placement=app_space3", headers=admin_headers)).json()

    assert [item["title"] for item in listed["items"]] == ["No espaço três"]


async def test_an_active_banner_answers_an_address_the_app_can_load(client, db, tenant, tenant_headers):
    await make_banner(db, tenant, image="images/banner/2026/07/30/summer.jpg")

    item = (await client.get("/api/banners/active", headers=tenant_headers)).json()["items"][0]

    assert item["imageUrl"] == "/media/images/banner/2026/07/30/summer.jpg"


async def test_a_window_is_checked_against_what_the_banner_already_says(client, db, tenant, admin_headers):
    """An update carries only what was set, so the end being moved is compared with the start already stored."""
    banner = await make_banner(db, tenant, starts_at=now() + timedelta(days=5), ends_at=now() + timedelta(days=10))

    response = await client.put(f"/api/banners/{banner.id}", json={"endsAt": (now() + timedelta(days=1)).isoformat()}, headers=admin_headers)

    assert response.status_code == 422
    assert response.json()["errors"]["endsAt"]


async def counted(client, db, tenant_headers, banner, kind: str, visitor: str | None = None):
    body = {"visitor": visitor} if visitor else {}

    return await client.post(f"/api/banners/{banner.uuid}/{kind}", json=body, headers=tenant_headers)


async def test_a_banner_is_named_outside_by_its_uuid_and_never_by_its_id(client, db, tenant, tenant_headers):
    banner = await make_banner(db, tenant)

    answer = (await client.get("/api/banners/active", headers=tenant_headers)).json()

    # The id says how many of them exist, so what a client counts a view by is the uuid.
    assert answer["items"][0]["uuid"] == banner.uuid
    assert "id" not in answer["items"][0]


async def test_a_view_is_counted_once_a_day_for_one_visitor(client, db, tenant, tenant_headers):
    banner = await make_banner(db, tenant)
    who = visitor.minted()

    assert (await counted(client, db, tenant_headers, banner, "view", who)).status_code == 204
    assert (await counted(client, db, tenant_headers, banner, "view", who)).status_code == 204

    await db.refresh(banner)

    # The second call is the same visitor on the same day, and the total is what it was.
    assert banner.views == 1


async def test_two_visitors_are_two_views(client, db, tenant, tenant_headers):
    banner = await make_banner(db, tenant)

    await counted(client, db, tenant_headers, banner, "view", visitor.minted())
    await counted(client, db, tenant_headers, banner, "view", visitor.minted())

    await db.refresh(banner)

    assert banner.views == 2


async def test_a_click_is_counted_apart_from_a_view(client, db, tenant, tenant_headers):
    banner = await make_banner(db, tenant)
    who = visitor.minted()

    await counted(client, db, tenant_headers, banner, "view", who)
    await counted(client, db, tenant_headers, banner, "click", who)

    await db.refresh(banner)

    assert (banner.views, banner.clicks) == (1, 1)


async def test_a_visitor_nobody_signed_counts_nothing(client, db, tenant, tenant_headers):
    banner = await make_banner(db, tenant)

    assert (await counted(client, db, tenant_headers, banner, "view", "not-a-signed-name")).status_code == 204

    await db.refresh(banner)

    # Whether a reader allowed being counted is never the business of the caller, so this is quiet and not an error.
    assert banner.views == 0


async def test_counting_a_banner_that_is_not_there_is_a_refusal(client, tenant_headers):
    answer = await client.post("/api/banners/00000000-0000-0000-0000-000000000000/view", json={}, headers=tenant_headers)

    assert answer.status_code == 404


async def test_a_banner_of_another_tenant_is_not_counted(client, db, tenant, tenant_headers):
    other = await make_tenant(db, code="other", domain="other.acme.com")
    banner = await make_banner(db, other)

    answer = await counted(client, db, tenant_headers, banner, "view", visitor.minted())

    assert answer.status_code == 404


async def test_a_banner_naming_a_language_answers_only_that_reader(client, db, tenant, tenant_headers):
    english = await make_language(db, code_iso_639_1="en", name="English")
    portuguese = await make_language(db, code_iso_639_1="pt", name="Portuguese")

    await make_banner(db, tenant, title="For english", language_id=english.id)
    await make_banner(db, tenant, title="For portuguese", language_id=portuguese.id)
    await make_banner(db, tenant, title="For everybody")

    answer = (await client.get("/api/banners/active", headers=tenant_headers | {"Accept-Language": "pt"})).json()
    titles = sorted(item["title"] for item in answer["items"])

    # A banner naming no language is the banner of every reader, exactly as a row naming no tenant is of every tenant.
    assert titles == ["For everybody", "For portuguese"]


async def test_an_application_is_handed_a_name_it_can_be_counted_by(client, db, tenant, tenant_headers):
    """Without this the body field was a door with no key: only this side signs a name, and nothing handed one out."""
    banner = await make_banner(db, tenant)

    handed = (await client.get("/api/meta/visitor")).json()["visitor"]

    assert (await counted(client, db, tenant_headers, banner, "view", handed)).status_code == 204

    await db.refresh(banner)

    assert banner.views == 1


async def test_the_name_an_application_is_handed_counts_once_a_day_like_any_other(client, db, tenant, tenant_headers):
    banner = await make_banner(db, tenant)
    handed = (await client.get("/api/meta/visitor")).json()["visitor"]

    await counted(client, db, tenant_headers, banner, "view", handed)
    await counted(client, db, tenant_headers, banner, "view", handed)

    await db.refresh(banner)

    assert banner.views == 1


async def test_deleting_a_banner_takes_the_impressions_that_counted_it(client, db, tenant, admin_headers, tenant_headers):
    """An impression is an edge and never a record, so it goes with either end of it."""
    banner = await make_banner(db, tenant)

    await counted(client, db, tenant_headers, banner, "view", visitor.minted())

    answer = await client.delete(f"/api/banners/{banner.id}", headers=admin_headers)

    assert answer.status_code == 204
    assert await db.scalar(select(func.count()).select_from(BannerImpression)) == 0
