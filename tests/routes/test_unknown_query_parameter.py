"""A filter nobody applies would answer the whole list, and whoever misspelled one would read it as filtered."""

import pytest


@pytest.mark.parametrize("path", ["/api/products", "/api/users", "/api/plans", "/api/banners"])
async def test_a_parameter_the_listing_does_not_know_is_refused(client, admin_headers, path):
    response = await client.get(f"{path}?inventado=1", headers=admin_headers)

    assert response.status_code == 422
    assert response.json()["code"] == "error.unknown-query-parameter"
    assert "inventado" in response.json()["detail"]


async def test_a_misspelled_filter_is_refused_instead_of_answering_everything(client, admin_headers):
    """Writing `tenant_id` in snake_case is the shape the API does not speak, and it used to be ignored."""
    response = await client.get("/api/products?tenant_id=1", headers=admin_headers)

    assert response.status_code == 422
    assert "tenant_id" in response.json()["detail"]


@pytest.mark.parametrize("query", ["active=talvez", "tenantId=abc"])
async def test_a_value_the_column_cannot_read_is_refused_instead_of_dropped(client, admin_headers, query):
    """The name is known and the value is not, and dropping it answers the whole list to somebody reading it as filtered."""
    response = await client.get(f"/api/products?{query}", headers=admin_headers)

    assert response.status_code == 422
    assert response.json()["code"] == "error.invalid-query-parameter"
    assert query.split("=")[0] in response.json()["detail"]


async def test_an_empty_filter_still_means_no_filter(client, admin_headers):
    """The admin sends the field cleared, and that is asking for everything rather than for nothing."""
    assert (await client.get("/api/products?tenantId=", headers=admin_headers)).status_code == 200


async def test_the_filters_the_listing_declares_are_accepted(client, admin_headers):
    assert (await client.get("/api/products?tenantId=1&active=true", headers=admin_headers)).status_code == 200


async def test_paging_search_and_ordering_are_never_taken_for_filters(client, admin_headers):
    assert (await client.get("/api/products?limit=5&offset=0&search=x&ordering=-id", headers=admin_headers)).status_code == 200


async def test_a_lookup_refuses_what_it_does_not_read(client, admin_headers):
    """A lookup answers a short list and takes no offset, so one sent is a caller expecting a page it will not get."""
    assert (await client.get("/api/products/lookup?search=x&limit=5", headers=admin_headers)).status_code == 200
    assert (await client.get("/api/products/lookup?offset=10", headers=admin_headers)).status_code == 422
