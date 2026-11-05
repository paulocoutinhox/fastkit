from uuid import NAMESPACE_URL, uuid5

from helpers.dates import now


def drawn(name: str) -> str:
    """The uuid a device would draw for an event, fixed by a short name so a test reads which event is which."""
    return str(uuid5(NAMESPACE_URL, name))


def build_batch(*names) -> dict:
    return {"events": [{"uuid": drawn(name), "name": "app_opened", "params": {"screen": "home"}, "occurred_at": now().isoformat()} for name in names]}


async def test_ingest_accepts_a_batch(client, tenant, tenant_headers):
    response = await client.post("/api/events", json=build_batch("a", "b"), headers=tenant_headers)

    assert response.status_code == 202
    assert response.json() == {"accepted": 2, "duplicated": 0}


async def test_ingest_counts_a_replayed_uuid_as_duplicated(client, tenant, tenant_headers):
    await client.post("/api/events", json=build_batch("a"), headers=tenant_headers)

    response = await client.post("/api/events", json=build_batch("a", "b"), headers=tenant_headers)

    assert response.json() == {"accepted": 1, "duplicated": 1}


async def test_ingest_attaches_the_caller_when_it_is_known(client, tenant, member, tenant_headers, member_headers, admin_headers):
    await client.post("/api/events", json=build_batch("a"), headers={**tenant_headers, **member_headers})

    listed = await client.get("/api/app-events", headers=admin_headers)

    assert listed.json()["items"][0]["user"]["username"] == "reader"


async def test_ingest_keeps_an_anonymous_batch(client, tenant, tenant_headers, admin_headers):
    await client.post("/api/events", json=build_batch("a"), headers=tenant_headers)

    listed = await client.get("/api/app-events", headers=admin_headers)

    assert listed.json()["items"][0]["user"] is None
    assert listed.json()["items"][0]["tenant"]["code"] == "acme"


async def test_ingest_ignores_a_broken_token(client, tenant, tenant_headers, admin_headers):
    headers = {**tenant_headers, "Authorization": "Bearer not-a-token"}

    response = await client.post("/api/events", json=build_batch("a"), headers=headers)

    assert response.status_code == 202


async def test_ingest_requires_at_least_one_event(client, tenant, tenant_headers):
    response = await client.post("/api/events", json={"events": []}, headers=tenant_headers)

    assert response.status_code == 422


async def test_ingest_requires_the_tenant_header(client, tenant):
    assert (await client.post("/api/events", json=build_batch("a"))).status_code == 422


async def test_events_start_pending(client, tenant, tenant_headers, admin_headers):
    await client.post("/api/events", json=build_batch("a"), headers=tenant_headers)

    listed = await client.get("/api/app-events?status=pending", headers=admin_headers)

    assert listed.json()["count"] == 1


async def test_a_moment_an_offset_carries_past_the_calendar_is_refused_where_it_is_read(client, tenant, tenant_headers):
    """It passed validation and overflowed while being stored, which answered five hundred on a route anybody reaches."""
    batch = {"events": [{"uuid": drawn("edge"), "name": "content-viewed", "occurredAt": "9999-12-31T23:59:59-01:00"}]}
    response = await client.post("/api/events", json=batch, headers=tenant_headers)

    assert response.status_code == 422
    assert response.json()["code"] == "error.validation"


async def test_a_number_that_json_cannot_hold_is_refused_where_it_is_read(client, tenant, tenant_headers):
    """SQLite stores a NaN and MySQL refuses the text that carries one, so the suite passed and production answered five hundred."""
    body = b'{"events": [{"uuid": "' + drawn("nan").encode() + b'", "name": "content-viewed", "occurredAt": "2026-01-01T00:00:00Z", "params": {"x": NaN}}]}'
    response = await client.post("/api/events", content=body, headers=tenant_headers | {"content-type": "application/json"})

    assert response.status_code == 422
    assert response.json()["code"] == "error.validation"


async def test_an_event_named_by_a_counter_is_refused_and_one_in_capitals_is_the_same_event(client, tenant, tenant_headers):
    """The key is unique across every account, so a device numbering its events from one would collide with every other, and the same uuid in capitals would be a second event."""
    counted = await client.post("/api/events", json={"events": [{"uuid": "1", "name": "app_opened", "occurredAt": now().isoformat()}]}, headers=tenant_headers)

    assert counted.status_code == 422
    assert counted.json()["errors"] == {"events.0.uuid": "This value has an invalid format."}

    await client.post("/api/events", json=build_batch("once"), headers=tenant_headers)
    shouted = await client.post("/api/events", json={"events": [{"uuid": drawn("once").upper(), "name": "app_opened", "occurredAt": now().isoformat()}]}, headers=tenant_headers)

    assert shouted.json() == {"accepted": 0, "duplicated": 1}


async def test_a_map_nested_past_what_a_column_holds_is_refused_where_it_arrives(client, tenant, tenant_headers):
    """SQLite would write it and every listing that reads it would answer a five hundred, and MySQL refuses it on the write."""
    batch = build_batch("a")
    deep = 1

    for _ in range(40):
        deep = {"a": deep}

    batch["events"][0]["params"] = deep
    response = await client.post("/api/events", json=batch, headers=tenant_headers)

    assert response.status_code == 422
    assert "too deep" in str(response.json()["errors"])
