from helpers.dates import now


def build_batch(*uuids) -> dict:
    return {"events": [{"uuid": value, "name": "app_opened", "params": {"screen": "home"}, "occurred_at": now().isoformat()} for value in uuids]}


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
