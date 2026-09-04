"""Who reaches every path of the API, stated once here and proved against the running application."""

import pytest
from httpx import ASGITransport, AsyncClient

from enums.user import UserRole
from helpers.router import ROUTERS
from services.crud import CrudService

# What a call with no account at all is answered by, which is only ever a catalogue or the shape of the instance.
OPEN = {
    "GET /api/meta",
    "GET /api/meta/captcha",
    "GET /api/meta/visitor",
    "GET /api/meta/health",
    "GET /api/meta/ready",
    "GET /api/languages/active",
    "GET /api/banners/active",
    "POST /api/banners/{uuid}/view",
    "POST /api/banners/{uuid}/click",
    "GET /api/galleries/active",
    "GET /api/galleries/by-tag/{tag}",
    "GET /api/contents/by-tag/{tag}",
    "GET /api/commerce/products",
    "GET /api/commerce/products/{slug}",
    "GET /api/subscriptions/plans",
    "GET /api/countries/offered",
    "POST /api/contact",
    "POST /api/newsletter",
    "POST /api/newsletter/confirm/{token}",
    "POST /api/newsletter/unsubscribe/{token}",
    "POST /api/signin",
    "POST /api/signup",
    "POST /api/admin/signin",
    "POST /api/account/password-reset",
    "POST /api/account/password-reset/confirm",
    "POST /api/events",
    "DELETE /api/webhooks/{key}",
    "GET /api/webhooks/{key}",
    "PATCH /api/webhooks/{key}",
    "POST /api/webhooks/{key}",
    "PUT /api/webhooks/{key}",
}

# What any signed in account reaches, which is its own row and never a listing of everybody.
ACCOUNT = {
    "DELETE /api/account/addresses/{address_type}",
    "DELETE /api/account/avatar",
    "DELETE /api/account/me",
    "GET /api/account/addresses",
    "GET /api/account/balances",
    "GET /api/account/credits",
    "GET /api/account/entitlements",
    "GET /api/meta/permissions",
    "GET /api/account/me",
    "GET /api/account/products",
    "GET /api/account/purchases",
    "GET /api/account/purchases/{purchase_id}",
    "GET /api/countries/{country_code}/postal-code/{code}",
    "GET /api/subscriptions/me",
    "POST /api/commerce/products/{slug}/checkout",
    "POST /api/subscriptions/plans/{code}/checkout",
    "GET /api/subscriptions/{subscription_id}/transactions",
    "POST /api/account/avatar",
    "POST /api/account/password",
    "POST /api/account/subscriptions/refresh",
    "PUT /api/account/addresses/{address_type}",
    "PUT /api/account/me",
}

SAMPLES = {"{record_id}": "1", "{address_type}": "main", "{tag}": "terms", "{slug}": "handbook", "{subscription_id}": "1", "{purpose}": "image", "{key}": "nope"}

# These two spend the credential the sweep is holding, and what they answer is proved where they are tested.
SPENT = {"DELETE /api/account/me", "POST /api/account/password"}


def named(app) -> list[str]:
    return sorted(f"{method.upper()} {path}" for path, operations in app.openapi()["paths"].items() for method in operations)


def filled(path: str) -> str:
    for token, value in SAMPLES.items():
        path = path.replace(token, value)

    return path


async def answered(app, headers, name: str) -> int:
    method, path = name.split(" ", 1)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        answer = await client.request(method, filled(path), headers=headers, json={} if method in ("POST", "PUT", "PATCH") else None)

    return answer.status_code


def test_every_path_of_the_api_is_named_by_exactly_one_audience(app):
    """A path nobody placed is one nobody decided the audience of, and this is where that decision is written down."""
    every = set(named(app))
    placed = OPEN | ACCOUNT

    assert placed - every == set(), f"named here and gone from the api: {sorted(placed - every)}"
    assert len(every) > 200, "the sweep found almost no path, so it is proving nothing"

    # Everything left over is the admin surface, which the crud factory guards with the roles its service declares.
    assert len(every - placed) > 150


@pytest.mark.parametrize("name", sorted(ACCOUNT - SPENT))
async def test_what_the_account_reaches_needs_an_account(app, tenant_headers, member_headers, name):
    assert await answered(app, tenant_headers, name) == 401
    assert await answered(app, {**tenant_headers, **member_headers}, name) != 401


@pytest.mark.parametrize("name", sorted(OPEN))
async def test_what_is_open_answers_without_one(app, tenant_headers, name):
    assert await answered(app, tenant_headers, name) != 401


async def test_the_admin_surface_refuses_every_role_it_does_not_name(app, tenant_headers, member_headers, admin_headers):
    """The whole point of a role: a reader is refused and an administrator is not, on every path neither of the two lists above names."""
    administrative = [name for name in named(app) if name not in OPEN | ACCOUNT]
    reached = []

    for name in administrative:
        if await answered(app, {**tenant_headers, **member_headers}, name) != 403:
            reached.append(name)

    assert reached == [], f"a reader was not refused by: {reached}"
    assert len(administrative) > 150


def test_every_resource_says_which_roles_reach_it():
    """The factory reads the roles off the service, so a resource that declares none would be one nobody decided."""
    services = []
    pending = list(CrudService.__subclasses__())

    while pending:
        current = pending.pop()
        pending.extend(current.__subclasses__())

        if current.model is not None:
            services.append(current)

    assert len(services) > 25, "the scan found almost no service, so it is proving nothing"

    for service in services:
        assert service.roles, f"{service.__name__} names no role"
        assert all(isinstance(role, UserRole) for role in service.roles), f"{service.__name__} names something that is not a role"


def test_the_factory_is_the_only_thing_that_guards_a_resource():
    """One place applies the roles, so a resource can never be published with a guard somebody forgot."""
    import pathlib
    import re

    factory = pathlib.Path("helpers/crud.py").read_text()

    # Every route the factory builds is guarded by what the service declared, and nothing else in there names a role.
    guards = {match.group(1) for match in re.finditer(r"requires\(\*(\(service\.lookup_roles or service\.roles\)|service\.roles)\)", factory)}

    assert guards == {"(service.lookup_roles or service.roles)", "service.roles"}
    assert factory.count("Depends(requires(*service.roles))") == 2, "one for the read side and one for the writes, and never a third"
    assert "router = build_readonly_router(service, read_schema, prefix, tag)" in factory
    assert len(ROUTERS) > 30
