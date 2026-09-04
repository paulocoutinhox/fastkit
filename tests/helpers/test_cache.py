"""What a surface assembles is kept, and a value no store could write down would leave the cache off without saying so."""

import logging
import pathlib
import re
from decimal import Decimal

import pytest
from cachefy.store.base import KEY_LIMIT

from helpers import cache
from models.base import BIG_INTEGER_MAX
from tests.factories import make_content, make_gallery, make_gallery_photo, make_plan, make_product


@pytest.fixture
async def caching(monkeypatch):
    monkeypatch.setattr(cache.settings.cache, "enabled", True)

    yield

    for space in cache.every():
        await space.clear()


def test_every_space_is_one_a_surface_reads_and_every_surface_reads_one():
    """A space nobody reads is a lifetime nobody honours, and a surface reading none of them is one this guard never drove."""
    written = [line for path in pathlib.Path("routes").rglob("*.py") for line in path.read_text().splitlines() if "cache.answered(" in line]
    read = {match.group(1) for line in written for match in re.finditer(r"cache\.answered\((?:.*?\bcache\.(\w+)\b)", line)}
    read |= {match.group(1) for line in written for match in re.finditer(r"cache\.(\w+) if ", line)}

    assert written, "the guard reads the surfaces it protects, so it proves nothing where it read none"
    assert read == {space.name for space in cache.every()}, f"the spaces declared and the ones a surface reads have drifted apart: {read ^ {space.name for space in cache.every()}}"


async def test_nothing_a_surface_assembles_is_refused_by_the_store(caching, caplog, client, site, db, tenant, tenant_headers):
    """A refused value is a warning and never an error, so a cache that quietly stopped keeping anything looks exactly like a slow one."""
    product = await make_product(db, tenant)
    await make_plan(db, tenant)
    content = await make_content(db, tenant)
    gallery = await make_gallery(db, tenant)

    await make_gallery_photo(db, gallery)

    addresses = [f"/api/commerce/products/{product.slug}", "/api/commerce/products", "/api/commerce/products?search=Product", "/api/subscriptions/plans", f"/api/contents/by-tag/{content.tag}", "/api/galleries/active", f"/api/galleries/by-tag/{gallery.tag}", "/api/banners/active"]
    pages = ["/", "/products", f"/products/{product.slug}", "/plans", "/gallery", f"/gallery/{gallery.tag}", f"/content/{content.tag}"]

    with caplog.at_level(logging.WARNING, logger="cachefy.space"):
        for address in addresses:
            assert (await client.get(address, headers=tenant_headers)).status_code == 200

        for address in pages:
            assert (await site.get(address)).status_code == 200

    refused = [record.getMessage() for record in caplog.records if "could not keep" in record.getMessage()]
    held = {space.name: await space.count() for space in cache.every()}

    assert refused == [], f"a surface assembled something no store can write down, so it is never cached: {refused}"
    # Every page of the site also settles which of the pages the navigation names this brand answers, and that is one entry and not one per address.
    assert sum(held.values()) == len(addresses) + len(pages) + 1, "every address driven here has to have left its answer behind"
    assert [name for name, count in held.items() if not count] == [], f"these spaces were driven and kept nothing: {held}"


async def test_one_space_going_stale_leaves_the_others_standing(caching, client, db, tenant, tenant_headers):
    """One lifetime for everything was one lifetime nobody could tune, so a space is cleared and read on its own."""
    await make_product(db, tenant)
    await make_plan(db, tenant)

    await client.get("/api/commerce/products", headers=tenant_headers)
    await client.get("/api/subscriptions/plans", headers=tenant_headers)

    await cache.products.clear()

    assert await cache.products.count() == 0
    assert await cache.plans.count() == 1


async def test_a_search_is_kept_apart_from_the_listing_it_narrows(caching, client, db, tenant, tenant_headers):
    """A term is an open set of keys and a listing is one, so they age on their own clocks."""
    await make_product(db, tenant, name="Alpha manual")

    await client.get("/api/commerce/products", headers=tenant_headers)
    await client.get("/api/commerce/products?search=Alpha", headers=tenant_headers)

    assert await cache.products.count() == 1
    assert await cache.search.count() == 1
    assert cache.search.ttl < cache.products.ttl


async def test_two_surfaces_of_one_thing_never_read_what_the_other_assembled(caching, client, site, db, tenant, tenant_headers):
    """The api and the site assemble the same product into different shapes, so the surface is part of the key."""
    product = await make_product(db, tenant)

    await client.get("/api/commerce/products", headers=tenant_headers)
    await site.get("/products")

    assert await cache.products.count() == 2
    assert cache.named(surface="api", tenant=tenant.id, language="en") != cache.named(surface="site", tenant=tenant.id, language="en")
    assert product.slug


async def test_a_page_holds_the_same_type_whether_the_cache_is_on_or_off(caching, site, db, tenant):
    """Money is a decimal on the page, and it stays one: what travels as text is read back through the schema that built it."""
    from schemas.commerce import SiteProductSchema

    await make_product(db, tenant, price=Decimal("19.90"))

    first = await site.get("/products")
    repeated = await site.get("/products")
    kept = await cache.products.get(cache.named(surface="site", tenant=tenant.id, language="en"))

    assert first.status_code == repeated.status_code == 200
    # A price is a decimal, and the wire carries the value rather than the number of zeros the column keeps it with.
    assert Decimal(kept[0]["price"]) == Decimal("19.90")
    assert SiteProductSchema(**kept[0]).price == Decimal("19.90")
    assert "19.90" in repeated.text


async def test_the_cache_of_a_machine_somebody_develops_on_keeps_nothing(client, db, tenant, tenant_headers):
    await make_product(db, tenant)

    await client.get("/api/commerce/products", headers=tenant_headers)

    assert sum([await space.count() for space in cache.every()]) == 0


def test_the_key_names_everything_that_changes_the_answer():
    parts = {"surface": "site", "tenant": 1, "language": "pt", "search": "x"}

    for name, other in (("surface", "api"), ("tenant", 2), ("language", "en"), ("search", "y")):
        assert cache.named(**parts) != cache.named(**parts | {name: other})

    assert cache.named(**parts) == cache.named(**parts)
    assert cache.named(surface="site", tenant=1) == cache.named(surface="site", tenant=1, search=None)


def test_no_surface_can_build_a_key_wider_than_the_column_that_holds_it():
    """A tag is as wide as its column, and a key past the limit is refused by MySQL or truncated into the key of another page."""
    import models.registry  # noqa: F401
    from helpers.db import Base

    widest = {name: "x" * (Base.metadata.tables[table].columns[column].type.length) for name, table, column in (("tag", "content", "tag"), ("slug", "commerce_product", "slug"), ("code", "subscription_plan", "code"))}
    built = [cache.named(surface=surface, tenant=BIG_INTEGER_MAX, language="pt", placement="app_space1", search="x" * 128, **widest) for surface in ("api", "site")]

    assert built
    assert max(len(space.name) + len(key) for space in cache.every() for key in built) <= KEY_LIMIT, "a key wider than its column is one page answering with what another page assembled"
