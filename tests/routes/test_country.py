"""The registry of countries, which is what says where an address may be written and who answers its postal code."""

from enums.country import PostalCodeProvider


async def test_a_code_is_kept_the_way_the_standard_writes_it(client, admin_headers):
    """The form of the site sends what the select carries, and an api client sends whatever it feels like."""
    created = await client.post("/api/countries", json={"name": "Brazil", "codeIso31661": "br", "postalCodeProvider": "viacep"}, headers=admin_headers)

    assert created.status_code == 201
    assert created.json()["codeIso31661"] == "BR"
    assert created.json()["postalCodeProvider"] == PostalCodeProvider.VIACEP


async def test_two_countries_never_share_a_code(client, admin_headers):
    payload = {"name": "Brazil", "codeIso31661": "BR"}

    assert (await client.post("/api/countries", json=payload, headers=admin_headers)).status_code == 201

    refused = await client.post("/api/countries", json={"name": "Brasil", "codeIso31661": "br"}, headers=admin_headers)

    assert refused.status_code == 409
    assert refused.json()["code"] == "error.code-already-used"


async def test_a_country_that_declares_no_provider_carries_none(client, admin_headers):
    created = await client.post("/api/countries", json={"name": "United Kingdom", "codeIso31661": "GB"}, headers=admin_headers)

    assert created.json()["postalCodeProvider"] is None


async def test_renaming_a_country_leaves_its_code_where_it_was(client, admin_headers):
    created = await client.post("/api/countries", json={"name": "Brazil", "codeIso31661": "BR"}, headers=admin_headers)
    changed = await client.put(f"/api/countries/{created.json()['id']}", json={"name": "Brasil"}, headers=admin_headers)

    assert changed.status_code == 200
    assert changed.json()["codeIso31661"] == "BR"


async def test_only_the_countries_that_are_offered_reach_the_form(db):
    from services.country import country_service
    from tests.factories import make_country

    await make_country(db)
    await make_country(db, name="Brazil", code_iso_3166_1="BR")
    await make_country(db, name="Nowhere", code_iso_3166_1="ZZ", active=False)

    offered = await country_service.list_offered(db)

    assert [country.code_iso_3166_1 for country in offered] == ["BR", "GB"]
    assert await country_service.find_by_code(db, "zz") is None
