"""Who changed what in the panel, because an operator moves money and a record with no author answers nobody."""

import pytest
from sqlalchemy import select

from enums.system_log import LogCategory
from models.system_log import SystemLog
from tests.factories import make_content_category


async def entries(db):
    return list((await db.execute(select(SystemLog).where(SystemLog.category == LogCategory.ADMIN).order_by(SystemLog.id.asc()))).scalars())


async def test_creating_writes_down_who_created_it(client, db, administrator, admin_headers):
    answer = await client.post("/api/content-categories", json={"name": "Guides"}, headers=admin_headers)
    written = await entries(db)

    assert len(written) == 1
    assert written[0].user_id == administrator.id
    assert written[0].meta["action"] == "created"
    assert written[0].meta["records"] == [answer.json()["id"]]


async def test_editing_and_deleting_are_written_down_too(client, db, admin_headers):
    category = await make_content_category(db, name="Guides")

    await client.put(f"/api/content-categories/{category.id}", json={"name": "Handbooks"}, headers=admin_headers)
    await client.delete(f"/api/content-categories/{category.id}", headers=admin_headers)

    assert [entry.meta["action"] for entry in await entries(db)] == ["edited", "deleted"]


async def test_reordering_names_every_record_it_moved(client, db, tenant, admin_headers):
    from tests.factories import make_gallery, make_gallery_photo

    gallery = await make_gallery(db, tenant)
    first = await make_gallery_photo(db, gallery, caption="One", position=0)
    second = await make_gallery_photo(db, gallery, caption="Two", position=1)

    await client.put("/api/gallery-photos/order", json={"ids": [second.id, first.id]}, headers=admin_headers)
    written = await entries(db)

    assert written[0].meta["action"] == "reordered"
    assert written[0].meta["records"] == [second.id, first.id]


async def test_nothing_of_the_body_reaches_the_record(client, db, tenant, admin_headers):
    """A payload carries a password and a gateway secret, and an audit trail is read by more people than the form was."""
    payload = {"tenantId": tenant.id, "provider": "stripe", "environment": "sandbox", "stripeApiKey": "sk_live_worth_money"}

    await client.post("/api/integrations", json=payload, headers=admin_headers)
    written = await entries(db)

    assert "sk_live_worth_money" not in str(written[0].meta)
    assert "sk_live_worth_money" not in written[0].description


async def test_a_read_writes_nothing_down(client, db, admin_headers):
    await client.get("/api/content-categories", headers=admin_headers)

    assert await entries(db) == []


@pytest.mark.parametrize("category", [LogCategory.ADMIN])
async def test_the_category_is_one_the_panel_can_filter_by(category):
    assert category in LogCategory


async def test_nobody_deletes_the_account_they_are_signed_in_with(client, administrator, admin_headers):
    """The trail of the deletion would point at somebody who is gone, and what came back was a conflict about a duplicate."""
    answer = await client.delete(f"/api/users/{administrator.id}", headers=admin_headers)

    assert answer.status_code == 422
    assert answer.json()["code"] == "error.cannot-delete-yourself"


async def test_another_account_is_deleted_as_it_always_was(client, db, tenant, member, admin_headers):
    assert (await client.delete(f"/api/users/{member.id}", headers=admin_headers)).status_code == 204
