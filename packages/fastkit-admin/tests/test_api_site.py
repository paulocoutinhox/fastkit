from decimal import Decimal

import httpx
import pytest

from fastkit_core.errors.exceptions import NotFoundError
from fastkit_admin.query import parse_grid_query
from fastkit_admin.site import AdminSite

ALL_PERMISSIONS = [
    "products.view",
    "products.create",
    "products.update",
    "products.delete",
]


def client_for(admin_app_factory, permissions=ALL_PERMISSIONS):
    app = admin_app_factory(permissions)

    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://admin"
    )


async def _seed(database, model):
    async with database.session_factory() as session:
        session.add(
            model(
                name="Alpha", price=Decimal("10.00"), category="general", is_active=True
            )
        )
        session.add(
            model(
                name="Beta", price=Decimal("20.00"), category="premium", is_active=False
            )
        )
        await session.commit()


async def test_navigation_is_grouped_and_permission_filtered(admin_app_factory):
    async with client_for(admin_app_factory) as client:
        groups = (await client.get("/navigation")).json()["data"]

        resources = (await client.get("/resources")).json()
        assert resources["data"][0]["label"] == "Products"

    keys = {group["key"] for group in groups}
    # catalog is visible (products.view granted), internal is hidden (no reports.view)
    assert "catalog" in keys
    assert "internal" not in keys

    catalog = next(group for group in groups if group["key"] == "catalog")
    assert any(item["resource"] == "products" for item in catalog["items"])


async def test_navigation_shows_permitted_group(admin_app_factory):
    async with client_for(
        admin_app_factory, permissions=[*ALL_PERMISSIONS, "reports.view"]
    ) as client:
        groups = (await client.get("/navigation")).json()["data"]

    assert "internal" in {group["key"] for group in groups}


async def test_schema_endpoint_includes_flags(admin_app_factory):
    async with client_for(admin_app_factory, permissions=["products.view"]) as client:
        body = (await client.get("/resources/products/schema")).json()

    grid = body["data"]["grid"]
    assert grid["resource"] == "products"
    assert body["data"]["form"]["mode"] == "create"
    # view-only: can list but not create/update/delete
    assert grid["flags"]["can_list"] is True
    assert grid["flags"]["can_create"] is False
    assert grid["flags"]["can_delete"] is False
    assert grid["columns"][1]["align"] == "right"


async def test_grid_row_endpoint(admin_app_factory):
    async with client_for(admin_app_factory) as client:
        created = await client.post(
            "/resources/products",
            json={
                "name": "RowFetch",
                "price": "5.00",
                "category": "general",
                "is_active": "true",
            },
        )
        identifier = created.json()["data"]["id"]

        row = (await client.get(f"/resources/products/{identifier}/row")).json()

        assert row["data"]["name"] == "RowFetch"


async def test_relation_options_endpoint(admin_app_factory):
    async with client_for(admin_app_factory, permissions=["products.view"]) as client:
        empty = (await client.get("/resources/products/options/owner_id")).json()
        assert empty["data"] == []

        filtered = (
            await client.get("/resources/products/options/owner_id?category=general")
        ).json()
        assert filtered["data"] == [{"value": 1, "label": "general owner"}]


async def test_row_and_bulk_actions(admin_app_factory, database, product_model):
    await _seed(database, product_model)

    async with client_for(admin_app_factory) as client:
        grid = (await client.get("/resources/products")).json()
        identifier = grid["data"][0]["id"]

        response = await client.post(
            f"/resources/products/{identifier}/actions/deactivate"
        )
        assert response.status_code == 200
        assert response.json()["data"]["deactivated"] == 1

        ids = [row["id"] for row in grid["data"]]
        bulk = await client.post(
            "/resources/products/actions/deactivate", json={"ids": ids}
        )
        assert bulk.json()["data"]["deactivated"] == len(ids)

        # the "touch" action has no permission, so authorization is skipped
        touch = await client.post(
            "/resources/products/actions/touch", json={"ids": ids}
        )
        assert touch.json()["data"]["affected"] == len(ids)


async def test_navigation_without_authorization(database, site):
    from fastapi import FastAPI

    from fastkit_admin.api import AdminDeps, build_admin_router

    app = FastAPI()

    async def get_session():
        async with database.session_factory() as active:
            yield active

    deps = AdminDeps(
        get_session=get_session,
        get_current_user=lambda: object(),
        get_locale=lambda: "en",
        authorize=None,
    )
    app.include_router(build_admin_router(site, deps))

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://admin"
    ) as client:
        groups = (await client.get("/navigation")).json()["data"]

    # with no authorizer every menu is visible, so both groups appear
    assert {group["key"] for group in groups} == {"catalog", "internal"}


async def test_grid_endpoint(admin_app_factory, database, product_model):
    await _seed(database, product_model)

    async with client_for(admin_app_factory) as client:
        body = (
            await client.get("/resources/products?sort=name&page=1&page_size=10")
        ).json()

    assert body["success"] is True
    assert body["meta"]["pagination"]["total_items"] == 2
    assert body["data"][0]["name"] == "Alpha"


async def test_create_update_delete_flow(admin_app_factory):
    async with client_for(admin_app_factory) as client:
        created = await client.post(
            "/resources/products",
            json={
                "name": "Gamma",
                "price": "1.234,50",
                "category": "general",
                "is_active": "true",
            },
        )
        assert created.status_code == 201
        assert created.json()["message"]["code"] == "products.created"

        identifier = created.json()["data"]["id"]

        detail = (await client.get(f"/resources/products/{identifier}")).json()
        assert detail["data"]["name"] == "Gamma"

        updated = await client.put(
            f"/resources/products/{identifier}",
            json={
                "name": "Gamma2",
                "price": "9.99",
                "category": "premium",
                "is_active": "false",
            },
        )
        assert updated.json()["data"]["name"] == "Gamma2"

        patched = await client.patch(
            f"/resources/products/{identifier}", json={"name": "Gamma3"}
        )
        assert patched.json()["data"]["name"] == "Gamma3"

        deleted = await client.delete(f"/resources/products/{identifier}")
        assert deleted.json()["message"]["code"] == "products.deleted"


async def test_create_validation_returns_envelope(admin_app_factory):
    async with client_for(admin_app_factory) as client:
        body = (
            await client.post("/resources/products", json={"name": "", "price": "x"})
        ).json()

    assert body["success"] is False
    assert body["message"]["code"] == "validation.failed"


async def test_permission_denied(admin_app_factory):
    async with client_for(admin_app_factory, permissions=["products.view"]) as client:
        response = await client.post(
            "/resources/products", json={"name": "X", "price": "1.00"}
        )

    assert response.status_code == 403
    assert response.json()["message"]["code"] == "authorization.denied"


async def test_unknown_resource_returns_404(admin_app_factory):
    async with client_for(admin_app_factory) as client:
        response = await client.get("/resources/ghosts")

    assert response.status_code == 404


async def test_resource_without_permission_skips_authorization(admin_app_factory):
    async with client_for(admin_app_factory, permissions=[]) as client:
        response = await client.get("/resources/open")

    assert response.status_code == 200


def test_site_register_duplicate_and_missing(product_admin_cls):
    site = AdminSite()
    site.register(product_admin_cls())

    with pytest.raises(ValueError, match="already registered"):
        site.register(product_admin_cls())

    with pytest.raises(NotFoundError):
        site.get("missing")


def test_parse_grid_query_range_filters():
    class Params:
        def __init__(self, items):
            self._items = items

        def multi_items(self):
            return self._items

        def get(self, key, default=None):
            for name, value in self._items:
                if name == key:
                    return value

            return default

    params = Params(
        [
            ("page", "2"),
            ("filter[name]", "abc"),
            ("filter[created_at][from]", "2026-01-01"),
            ("filter[created_at][to]", "2026-12-31"),
            ("other", "x"),
        ]
    )
    query = parse_grid_query(params)

    assert query.page == 2
    assert query.filters["name"] == "abc"
    assert query.filters["created_at"] == {"from": "2026-01-01", "to": "2026-12-31"}

    # a mixed scalar-then-range key for the same field must not raise
    mixed = parse_grid_query(
        Params([("filter[price]", "5"), ("filter[price][from]", "1")])
    )
    assert mixed.filters["price"] == {"from": "1"}


def test_parse_grid_query_defaults():
    class Empty:
        def multi_items(self):
            return []

        def get(self, key, default=None):
            return default

    query = parse_grid_query(Empty())

    assert query.page == 1
    assert query.page_size == 25
