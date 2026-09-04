from enums.integration import Environment, Provider
from helpers.security import decrypt
from services.integration import integration_service
from tests.factories import make_integration, make_plan, make_tenant


async def test_create_never_answers_a_key_it_was_given(client, db, tenant, admin_headers):
    payload = {"tenant_id": tenant.id, "provider": Provider.REVENUECAT, "revenuecat_api_key": "sk-live-123", "revenuecat_webhook_secret": "whsec-456"}

    response = await client.post("/api/integrations", json=payload, headers=admin_headers)

    assert response.status_code == 201
    assert "revenuecatApiKey" not in response.json()
    assert response.json()["hasRevenuecatApiKey"] is True
    assert response.json()["hasRevenuecatWebhookSecret"] is True


async def test_a_key_is_stored_encrypted_in_the_column_named_after_its_gateway(client, db, tenant, admin_headers):
    payload = {"tenant_id": tenant.id, "provider": Provider.REVENUECAT, "revenuecat_api_key": "sk-live-123"}

    created = await client.post("/api/integrations", json=payload, headers=admin_headers)
    integration = await integration_service.get(db, created.json()["id"])

    assert integration.revenuecat_api_key_encrypted != "sk-live-123"
    assert decrypt(integration.revenuecat_api_key_encrypted) == "sk-live-123"


async def test_the_gateway_says_which_of_its_keys_proves_a_call_came_from_it(client, db, tenant, admin_headers):
    payload = {"tenant_id": tenant.id, "provider": Provider.REVENUECAT, "revenuecat_webhook_secret": "whsec-456"}

    created = await client.post("/api/integrations", json=payload, headers=admin_headers)
    integration = await integration_service.get(db, created.json()["id"])

    assert integration_service.read_webhook_secret(integration) == "whsec-456"


async def test_one_integration_per_provider_and_tenant(client, db, tenant, admin_headers):
    await make_integration(db, tenant)

    response = await client.post("/api/integrations", json={"tenantId": tenant.id, "provider": Provider.STRIPE}, headers=admin_headers)

    assert response.status_code == 409


async def test_several_providers_run_side_by_side(client, db, tenant, admin_headers):
    await make_integration(db, tenant)

    response = await client.post("/api/integrations", json={"tenantId": tenant.id, "provider": Provider.REVENUECAT}, headers=admin_headers)

    assert response.status_code == 201
    assert (await client.get("/api/integrations", headers=admin_headers)).json()["count"] == 2


async def test_external_product_uppercases_the_reference_currency(client, db, tenant, admin_headers):
    integration = await make_integration(db, tenant)
    plan = await make_plan(db, tenant)

    payload = {"integration_id": integration.id, "plan_id": plan.id, "external_id": "prod_1", "reference_currency": "brl", "reference_price": "19.90"}
    response = await client.post("/api/external-products", json=payload, headers=admin_headers)

    assert response.status_code == 201
    assert response.json()["referenceCurrency"] == "BRL"
    assert response.json()["plan"]["code"] == "monthly"


async def test_external_id_is_unique_inside_an_integration(client, db, tenant, admin_headers):
    integration = await make_integration(db, tenant)
    plan = await make_plan(db, tenant)

    payload = {"integration_id": integration.id, "plan_id": plan.id, "external_id": "prod_1"}

    assert (await client.post("/api/external-products", json=payload, headers=admin_headers)).status_code == 201
    assert (await client.post("/api/external-products", json=payload, headers=admin_headers)).status_code == 409


async def test_deleting_an_integration_takes_its_external_products(client, db, tenant, admin_headers):
    integration = await make_integration(db, tenant)
    plan = await make_plan(db, tenant)

    await client.post("/api/external-products", json={"integrationId": integration.id, "planId": plan.id, "externalId": "prod_1"}, headers=admin_headers)

    assert (await client.delete(f"/api/integrations/{integration.id}", headers=admin_headers)).status_code == 204
    assert (await client.get("/api/external-products", headers=admin_headers)).json()["count"] == 0


async def test_environment_defaults_to_production(client, db, tenant, admin_headers):
    response = await client.post("/api/integrations", json={"tenantId": tenant.id, "provider": Provider.STRIPE}, headers=admin_headers)

    assert response.json()["environment"] == Environment.PRODUCTION


async def test_the_lookup_names_an_integration_by_the_tenant_that_holds_it(db, tenant, admin_headers, client):
    """One gateway serves every tenant, so a list of three RevenueCat says nothing without the tenant."""
    other = await make_tenant(db, code="nik", name="Nik")

    await make_integration(db, tenant, provider=Provider.REVENUECAT)
    await make_integration(db, other, provider=Provider.REVENUECAT)

    listed = (await client.get("/api/integrations/lookup", headers=admin_headers)).json()["items"]

    assert sorted(item["label"] for item in listed) == sorted([f"{tenant.name} - RevenueCat", f"{other.name} - RevenueCat"])


async def test_editing_an_integration_keeps_the_address_a_gateway_already_posts_to(client, db, tenant, admin_headers):
    created = await client.post("/api/integrations", json={"tenant_id": tenant.id, "provider": Provider.REVENUECAT, "revenuecat_api_key": "sk-live-123"}, headers=admin_headers)
    born_with = created.json()["webhookKey"]

    edited = await client.put(f"/api/integrations/{created.json()['id']}", json={"environment": Environment.SANDBOX}, headers=admin_headers)

    assert edited.status_code == 200
    assert edited.json()["webhookKey"] == born_with


async def test_a_secret_nobody_typed_again_survives_the_save_and_one_sent_empty_is_cleared(client, db, tenant, admin_headers):
    created = await client.post("/api/integrations", json={"tenant_id": tenant.id, "provider": Provider.REVENUECAT, "revenuecat_api_key": "sk-live-123"}, headers=admin_headers)
    record_id = created.json()["id"]

    kept = await client.put(f"/api/integrations/{record_id}", json={"environment": Environment.SANDBOX}, headers=admin_headers)

    assert kept.json()["hasRevenuecatApiKey"] is True
    assert decrypt((await integration_service.get(db, record_id)).revenuecat_api_key_encrypted) == "sk-live-123"

    cleared = await client.put(f"/api/integrations/{record_id}", json={"revenuecat_api_key": None}, headers=admin_headers)

    assert cleared.json()["hasRevenuecatApiKey"] is False
