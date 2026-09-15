from enums.system_log import LogCategory, LogLevel
from services.system_log import system_log_service


async def recorded(db, tenant, member, level: LogLevel, description: str, category: LogCategory | None = None):
    entry = await system_log_service.record(db, tenant.id, member.id if member else None, level, category, description, {})
    await db.commit()

    return entry


async def test_the_trail_takes_no_entry_from_a_client(client, tenant_headers, member_headers):
    """An audit trail somebody can write into stops being one, so nothing outside this side files an entry."""
    for headers in ({}, tenant_headers, {**tenant_headers, **member_headers}):
        response = await client.post("/api/system-logs/report", json={"level": LogLevel.ERROR, "description": "forjado"}, headers=headers)

        assert response.status_code == 405


async def test_the_trail_is_read_only_even_for_an_administrator(client, admin_headers):
    """What a cron wrote is what happened, and a correction by hand would make the record disagree with its own origin."""
    assert (await client.post("/api/system-logs", json={"level": LogLevel.INFO, "description": "a mao"}, headers=admin_headers)).status_code == 405
    assert (await client.put("/api/system-logs/1", json={"description": "reescrito"}, headers=admin_headers)).status_code == 405
    assert (await client.delete("/api/system-logs/1", headers=admin_headers)).status_code == 405


async def test_an_entry_carries_the_tenant_and_the_author_this_side_resolved(client, db, tenant, member, admin_headers):
    await recorded(db, tenant, member, LogLevel.WARNING, "slow network")

    listed = await client.get("/api/system-logs", headers=admin_headers)

    assert listed.json()["items"][0]["tenant"]["code"] == "acme"
    assert listed.json()["items"][0]["user"]["username"] == "reader"


async def test_filter_by_level(client, db, tenant, member, admin_headers):
    await recorded(db, tenant, member, LogLevel.ERROR, "one")
    await recorded(db, tenant, member, LogLevel.INFO, "two")

    assert (await client.get("/api/system-logs?level=error", headers=admin_headers)).json()["count"] == 1


async def test_search_matches_the_description(client, db, tenant, member, admin_headers):
    await recorded(db, tenant, member, LogLevel.ERROR, "playback failed")

    assert (await client.get("/api/system-logs?search=playback", headers=admin_headers)).json()["count"] == 1
