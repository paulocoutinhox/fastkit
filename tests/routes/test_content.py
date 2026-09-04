from tests.factories import make_content, make_content_category, make_language


async def test_category_derives_the_tag(client, admin_headers):
    response = await client.post("/api/content-categories", json={"name": "Legal Notices"}, headers=admin_headers)

    assert response.status_code == 201
    assert response.json()["tag"] == "legal-notices"


async def test_category_refuses_a_duplicated_tag(client, db, admin_headers):
    await make_content_category(db)

    response = await client.post("/api/content-categories", json={"name": "Other", "tag": "legal"}, headers=admin_headers)

    assert response.status_code == 409
    assert response.json()["errors"]["tag"]


async def test_content_derives_the_tag_from_the_title(client, admin_headers):
    response = await client.post("/api/contents", json={"title": "Privacy Policy"}, headers=admin_headers)

    assert response.json()["tag"] == "privacy-policy"


async def test_content_relations_are_answered_expanded(client, db, tenant, admin_headers):
    category = await make_content_category(db)
    language = await make_language(db)

    payload = {"title": "Terms", "tenant_id": tenant.id, "category_id": category.id, "language_id": language.id}
    created = await client.post("/api/contents", json=payload, headers=admin_headers)

    assert created.json()["category"]["tag"] == "legal"
    assert created.json()["language"]["name"] == "English"
    assert created.json()["tenant"]["code"] == "acme"


async def test_read_by_tag_answers_the_tenant_version_first(client, db, tenant, tenant_headers):
    await make_content(db, None, title="Shared terms")
    await make_content(db, tenant, title="Acme terms")

    response = await client.get("/api/contents/by-tag/terms", headers=tenant_headers)

    assert response.status_code == 200
    assert response.json()["title"] == "Acme terms"


async def test_read_by_tag_falls_back_to_the_shared_version(client, db, tenant, tenant_headers):
    await make_content(db, None, title="Shared terms")

    response = await client.get("/api/contents/by-tag/terms", headers=tenant_headers)

    assert response.json()["title"] == "Shared terms"


async def test_read_by_tag_ignores_an_inactive_content(client, db, tenant, tenant_headers):
    await make_content(db, tenant, active=False)

    assert (await client.get("/api/contents/by-tag/terms", headers=tenant_headers)).status_code == 404


async def test_read_by_tag_answers_not_found_for_an_unknown_tag(client, tenant, tenant_headers):
    assert (await client.get("/api/contents/by-tag/nothing", headers=tenant_headers)).status_code == 404


async def test_language_codes_are_stored_lowercase(client, admin_headers):
    payload = {"name": "Portuguese", "native_name": "Português", "code_iso_639_1": "PT", "code_iso_language": "PT-BR"}
    response = await client.post("/api/languages", json=payload, headers=admin_headers)

    assert response.json()["codeIso6391"] == "pt"
    assert response.json()["codeIsoLanguage"] == "pt-br"


async def test_language_refuses_a_duplicated_code(client, db, admin_headers):
    await make_language(db)

    payload = {"name": "English UK", "native_name": "English", "code_iso_639_1": "EN", "code_iso_language": "en-gb"}
    response = await client.post("/api/languages", json=payload, headers=admin_headers)

    assert response.status_code == 409


async def test_active_languages_are_public(client, db):
    await make_language(db)
    await make_language(db, name="Klingon", code_iso_639_1="tlh", code_iso_language="tlh", active=False)

    response = await client.get("/api/languages/active")

    assert response.status_code == 200
    assert response.json()["count"] == 1
