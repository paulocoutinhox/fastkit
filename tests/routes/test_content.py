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


async def test_the_languages_an_application_offers_are_the_ones_an_account_may_keep(client, db):
    """An active row this instance does not offer is one the account would refuse, so an application is never handed it to offer."""
    await make_language(db)
    await make_language(db, name="Deutsch", native_name="Deutsch", code_iso_639_1="de", code_iso_language="de-de")
    await make_language(db, name="Klingon", code_iso_639_1="tlh", code_iso_language="tlh", active=False)

    response = await client.get("/api/languages/active")

    assert response.status_code == 200
    assert [language["codeIso6391"] for language in response.json()] == ["en"]


async def test_a_reader_gets_the_page_and_never_what_the_operator_keeps_about_it(client, db, tenant, tenant_headers):
    """The free map of an operator can name storage keys, and a client reads addresses and never keys."""
    await make_content(db, tenant, title="Acme terms", meta={"draft": "images/content/2026/01/01/secret.webp"})

    answered = (await client.get("/api/contents/by-tag/terms", headers=tenant_headers)).json()

    assert set(answered) == {"uuid", "title", "tag", "content", "publishedAt"}


async def test_the_language_of_a_page_is_the_one_the_caller_asked_for(client, db, tenant, tenant_headers):
    from tests.factories import make_language

    portuguese = await make_language(db, code_iso_639_1="pt", code_iso_language="pt-br", name="Portuguese")

    await make_content(db, tenant, title="Acme terms")
    await make_content(db, tenant, title="Termos da Acme", language_id=portuguese.id)

    answered = await client.get("/api/contents/by-tag/terms", headers=tenant_headers | {"accept-language": "pt-BR"})

    assert answered.json()["title"] == "Termos da Acme"


async def test_the_panel_is_told_where_a_page_lives_on_the_site_of_its_own_brand(client, db, tenant, admin_headers):
    """The panel may be open on any brand's domain, so the address of a page is answered by the one side that knows each brand's site."""
    from helpers.settings import settings

    own = await make_content(db, tenant, title="Terms", tag="terms")
    shared = await make_content(db, None, title="About", tag="about")

    answered = {item["id"]: item["address"] for item in (await client.get("/api/contents", headers=admin_headers)).json()["items"]}

    assert answered[own.id] == f"{settings.site.scheme}://{tenant.domain}/content/terms"
    # A page with a name of its own is linked at that name, and never at the address that moves to it.
    assert answered[shared.id] == "/about", "a shared page is on every site, so it is the path alone"
