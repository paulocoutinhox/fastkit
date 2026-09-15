from sqlalchemy import event

from helpers.db import async_engine
from tests.factories import make_gallery, make_gallery_photo


async def counted_queries(action) -> int:
    """How many statements one call costs, which is what tells a listing that reads its rows once from one that reads them per row."""
    counted = []

    def count(*arguments):
        counted.append(1)

    event.listen(async_engine.sync_engine, "before_cursor_execute", count)

    try:
        await action()
    finally:
        event.remove(async_engine.sync_engine, "before_cursor_execute", count)

    return len(counted)


async def test_the_listing_costs_the_same_however_many_galleries_there_are(client, db, tenant, tenant_headers):
    """A photo read per gallery was a query per gallery on the listing an application opens first."""

    async def listed():
        await client.get("/api/galleries/active", headers=tenant_headers)

    for index in range(2):
        await make_gallery_photo(db, await make_gallery(db, tenant, tag=f"few-{index}", active=True), position=0)

    few = await counted_queries(listed)

    for index in range(12):
        await make_gallery_photo(db, await make_gallery(db, tenant, tag=f"many-{index}", active=True), position=0)

    assert await counted_queries(listed) == few


async def test_the_listing_answers_every_gallery_with_its_own_photos(client, db, tenant, tenant_headers):
    """Grouping the photos of many galleries at once is only right if each one keeps exactly its own."""
    office = await make_gallery(db, tenant, title="Our office", tag="office", active=True)
    studio = await make_gallery(db, tenant, title="The studio", tag="studio", active=True)

    await make_gallery_photo(db, office, caption="Reception", position=0)
    await make_gallery_photo(db, studio, caption="The desk", position=0)
    await make_gallery_photo(db, studio, caption="The window", position=1)

    answered = (await client.get("/api/galleries/active", headers=tenant_headers)).json()["items"]
    drawn = {item["tag"]: [photo["caption"] for photo in item["photos"]] for item in answered}

    assert drawn == {"office": ["Reception"], "studio": ["The desk", "The window"]}


async def test_a_gallery_with_no_photo_at_all_is_still_listed(client, db, tenant, tenant_headers):
    """Grouping answers nothing for a gallery nobody added a photo to, and that is a card without a cover and never a missing row."""
    await make_gallery(db, tenant, title="Empty", tag="empty", active=True)

    answered = (await client.get("/api/galleries/active", headers=tenant_headers)).json()["items"]

    assert [(item["tag"], item["coverUrl"], item["photos"]) for item in answered] == [("empty", None, [])]
