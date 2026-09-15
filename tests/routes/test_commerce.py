import pytest

from helpers import cache
from services.commerce import commerce_service
from tests.factories import make_product


@pytest.fixture
async def caching(monkeypatch):
    """The suite leaves the cache off like the machine somebody develops on, so a test about it turns it on for itself."""
    monkeypatch.setattr(cache.settings.cache, "enabled", True)

    yield

    for space in cache.every():
        await space.clear()


async def test_a_product_search_keeps_the_assembled_answer_under_the_term(caching, client, db, tenant, tenant_headers):
    product = await make_product(db, tenant, name="Alpha manual")
    await make_product(db, tenant, name="Beta guide")

    first = await client.get("/api/commerce/products?search=Alpha", headers=tenant_headers)

    product.name = "Changed manual"
    await db.commit()

    repeated = await client.get("/api/commerce/products?search=Alpha", headers=tenant_headers)
    another_key = await client.get("/api/commerce/products?search=Changed", headers=tenant_headers)

    assert [item["name"] for item in first.json()["items"]] == ["Alpha manual"]
    assert repeated.json() == first.json()
    assert [item["name"] for item in another_key.json()["items"]] == ["Changed manual"]


async def test_the_shared_catalogue_never_keeps_one_accounts_ownership(caching, client, db, tenant, member, member_headers, tenant_headers):
    product = await make_product(db, tenant)

    anonymous = await client.get("/api/commerce/products", headers=tenant_headers)
    await commerce_service.grant(db, member.id, product.id, "test")
    signed_in = await client.get("/api/commerce/products", headers=member_headers | tenant_headers)

    kept = await cache.products.get(cache.named(surface="api", tenant=tenant.id, language="en"))

    assert anonymous.json()["items"][0]["owned"] is False
    assert signed_in.json()["items"][0]["owned"] is True
    assert "owned" not in kept[0]


async def test_the_catalogue_is_asked_of_the_database_once_while_the_answer_stands(caching, client, db, tenant, tenant_headers):
    await make_product(db, tenant)
    asked = []

    original = cache.products.fetch

    async def counted(key, producer, **spans):
        asked.append(key)

        return await original(key, producer, **spans)

    cache.products.fetch = counted

    try:
        await client.get("/api/commerce/products", headers=tenant_headers)
        await client.get("/api/commerce/products", headers=tenant_headers)
    finally:
        cache.products.fetch = original

    assert len(asked) == 2
    assert len(set(asked)) == 1


async def test_the_cache_of_a_machine_somebody_develops_on_keeps_nothing(client, db, tenant, tenant_headers):
    product = await make_product(db, tenant, name="Before")

    await client.get("/api/commerce/products", headers=tenant_headers)

    product.name = "After"
    await db.commit()

    answer = await client.get("/api/commerce/products", headers=tenant_headers)

    assert [item["name"] for item in answer.json()["items"]] == ["After"]
