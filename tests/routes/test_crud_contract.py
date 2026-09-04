import ast
import importlib
import pathlib

import pytest
from sqlalchemy.orm import class_mapper

from helpers.router import RESOURCES

ADMIN_PREFIXES = [
    "/api/tenants",
    "/api/languages",
    "/api/countries",
    "/api/users",
    "/api/contents",
    "/api/content-categories",
    "/api/banners",
    "/api/galleries",
    "/api/gallery-photos",
    "/api/products",
    "/api/purchases",
    "/api/user-products",
    "/api/user-addresses",
    "/api/plans",
    "/api/entitlements",
    "/api/plan-entitlements",
    "/api/benefits",
    "/api/subscriptions",
    "/api/user-entitlements",
    "/api/subscription-benefits",
    "/api/benefit-grants",
    "/api/integrations",
    "/api/external-products",
    "/api/webhook-events",
    "/api/app-events",
    "/api/system-logs",
    "/api/outbound-emails",
    "/api/credit-transactions",
]


@pytest.mark.parametrize("prefix", ADMIN_PREFIXES)
async def test_listing_requires_a_token(client, prefix):
    assert (await client.get(prefix)).status_code == 401


@pytest.mark.parametrize("prefix", ADMIN_PREFIXES)
async def test_listing_refuses_a_role_the_resource_does_not_name(client, member_headers, prefix):
    response = await client.get(prefix, headers=member_headers)

    assert response.status_code == 403
    assert response.json()["code"] == "error.role-not-allowed"


@pytest.mark.parametrize("prefix", ADMIN_PREFIXES)
async def test_listing_answers_a_page_to_an_administrator(client, admin_headers, prefix):
    response = await client.get(prefix, headers=admin_headers)

    assert response.status_code == 200
    assert response.json() == {"count": response.json()["count"], "limit": 50, "offset": 0, "items": response.json()["items"]}


@pytest.mark.parametrize("prefix", ADMIN_PREFIXES)
async def test_lookup_answers_labelled_options(client, admin_headers, prefix):
    response = await client.get(f"{prefix}/lookup", headers=admin_headers)

    assert response.status_code == 200
    assert "items" in response.json()


async def test_lookup_names_one_option_by_its_id(client, admin_headers, tenant):
    """A form holding a value the first page of options does not carry still shows the label the API builds."""
    response = await client.get(f"/api/tenants/lookup/{tenant.id}", headers=admin_headers)

    assert response.status_code == 200
    assert response.json() == {"id": tenant.id, "label": "Acme - acme"}


@pytest.mark.parametrize("prefix", ADMIN_PREFIXES)
async def test_naming_an_unknown_option_answers_not_found(client, admin_headers, prefix):
    response = await client.get(f"{prefix}/lookup/999999", headers=admin_headers)

    assert response.status_code == 404
    assert response.json()["code"] == "error.not-found"


@pytest.mark.parametrize("prefix", ADMIN_PREFIXES)
async def test_reading_an_unknown_record_answers_not_found(client, admin_headers, prefix):
    response = await client.get(f"{prefix}/999999", headers=admin_headers)

    assert response.status_code == 404
    assert response.json()["code"] == "error.not-found"


READ_ONLY_PREFIXES = ["/api/user-entitlements", "/api/subscription-benefits", "/api/benefit-grants", "/api/webhook-events", "/api/outbound-emails", "/api/newsletter-subscriptions"]


@pytest.mark.parametrize("prefix", READ_ONLY_PREFIXES)
async def test_delivery_tables_accept_no_writes(client, admin_headers, prefix):
    assert (await client.post(prefix, json={}, headers=admin_headers)).status_code == 405
    assert (await client.put(f"{prefix}/1", json={}, headers=admin_headers)).status_code == 405
    assert (await client.delete(f"{prefix}/1", headers=admin_headers)).status_code == 405


def bound_routers() -> list[tuple]:
    """Every service paired with the read schema its router answers, read from the calls that pair them."""
    pairs = []

    for path in sorted(pathlib.Path("routes").glob("*.py")):
        module = importlib.import_module(f"routes.{path.stem}")
        tree = ast.parse(path.read_text())

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or getattr(node.func, "id", "") not in ("build_router", "build_readonly_router"):
                continue

            service, schema = (getattr(module, argument.id) for argument in node.args[:2])
            pairs.append((path.stem, service, schema))

    return pairs


@pytest.mark.parametrize("module, service, schema", bound_routers(), ids=lambda value: getattr(value, "__name__", value if isinstance(value, str) else type(value).__name__))
def test_every_relation_a_read_schema_answers_is_a_relation_the_service_loads(module, service, schema):
    """A relation nobody eager loaded is a MissingGreenlet the moment the row is serialized."""
    eager = {path.split(".")[0] for path in service.relations}
    available = {relation.key for relation in class_mapper(service.model).relationships}

    assert {name for name in schema.model_fields if name in available} <= eager


@pytest.mark.parametrize("prefix", ADMIN_PREFIXES)
async def test_an_ordering_the_list_does_not_answer_is_refused(client, admin_headers, prefix):
    """Answering a different order than the one that was asked for is a lie the caller cannot see."""
    response = await client.get(f"{prefix}?ordering=nao-existe-esse-campo", headers=admin_headers)

    assert response.status_code == 422
    assert response.json()["code"] == "error.ordering-not-allowed"


@pytest.mark.parametrize("prefix", ADMIN_PREFIXES)
async def test_the_list_answers_its_own_default_ordering(client, admin_headers, prefix):
    assert (await client.get(prefix, headers=admin_headers)).status_code == 200


def deletes(app) -> set:
    """The addresses the application answers a deletion on, read off the route table because that is what is served."""
    found = set()

    for included in app.routes:
        context = getattr(included, "include_context", None)
        prefix = context.prefix if context else ""

        for route in getattr(getattr(included, "original_router", None), "routes", [included]):
            if "DELETE" in getattr(route, "methods", ()):
                found.add(f"{prefix}{route.path}")

    return found


@pytest.mark.parametrize("name", sorted(RESOURCES))
async def test_deleting_a_record_that_is_not_there_answers_the_same_everywhere(app, client, admin_headers, name):
    """A resource that deletes says not found, one that does not says the method is not there, and neither says 500."""
    expected = 404 if f"/api/{name}/{{record_id}}" in deletes(app) else 405

    assert (await client.delete(f"/api/{name}/2147483647", headers=admin_headers)).status_code == expected


def test_this_file_still_walks_every_resource_the_application_serves():
    assert len(RESOURCES) == 31


async def test_a_second_row_addressed_by_the_same_tag_is_refused(client, admin_headers, db):
    """That tag is an address, so two rows sharing it inside one language would leave one of them open by nothing."""
    from tests.factories import make_content_category

    category = await make_content_category(db)
    await db.commit()

    payload = {"categoryId": category.id, "content": "<p>x</p>", "tag": "twice"}

    first = await client.post("/api/contents", json={**payload, "title": "First"}, headers=admin_headers)
    second = await client.post("/api/contents", json={**payload, "title": "Second"}, headers=admin_headers)

    assert first.status_code == 201
    assert second.status_code == 409
    assert second.json()["code"] == "error.duplicated-record"


async def test_a_filter_that_names_a_row_nobody_has_narrows_to_nothing(client, admin_headers, db, tenant):
    """These read a value against one table to narrow another, and a null scope reads as the shared rows rather than as no rows at all."""
    from helpers.router import RESOURCES
    from tests.factories import make_product

    # A null scope is what reads as the shared rows, so one of those is what makes the wrong answer visible at all.
    await make_product(db, tenant)
    await make_product(db, None, slug="shared-one")
    await db.commit()

    driven = 0

    for name, service in sorted(RESOURCES.items()):
        for field in getattr(service, "filters_elsewhere", {}):
            wire = field.split("_")[0] + "".join(part.title() for part in field.split("_")[1:])
            driven += 1

            answer = await client.get(f"/api/{name}?limit=50", params={wire: 999999999}, headers=admin_headers)

            assert answer.status_code == 200, f"{name}.{wire} answered {answer.status_code}"
            assert answer.json()["count"] == 0, f"{name}.{wire} names a row nobody has and answers {answer.json()['count']} rows"

    assert driven >= 5, "the guard read too few of these filters to claim anything"
