"""Who reaches what, said in one line on a service and answered the same way by the API and by the panel."""

import pathlib
import re

import pytest
from httpx import ASGITransport, AsyncClient

from enums.user import PANEL_ROLES, UserRole, UserStatus
from helpers.crud import RESOURCES
from helpers.security import create_token
from services.user import user_service

# What the example role is given, which is the pages of the site and nothing that moves money.
EDITED = {"contents", "content-categories", "galleries", "gallery-photos", "banners"}


@pytest.fixture
async def editor(db):
    return await user_service.create(db, {"username": "editor", "email": "editor@acme.com", "password": "s3cret-password", "role": UserRole.EDITOR, "status": UserStatus.ACTIVE})


@pytest.fixture
def editor_headers(editor):
    return {"Authorization": f"Bearer {create_token(editor.token, editor.role, editor.session_epoch)}"}


def test_who_works_in_the_panel_is_named_and_never_derived():
    """Every role but one would hand the panel to a role added later on the day it is written, and nobody would have decided that."""
    source = pathlib.Path("enums/user.py").read_text()
    declared = re.search(r"^PANEL_ROLES = (.+)$", source, re.M).group(1)

    assert "for role in" not in declared and "if role" not in declared, f"who reaches the panel is derived rather than named: {declared}"
    assert PANEL_ROLES == (UserRole.EDITOR, UserRole.ADMINISTRATOR)
    assert UserRole.NORMAL not in PANEL_ROLES


async def test_the_panel_takes_the_roles_that_work_in_it(client, editor):
    """The role never travels to the panel: what it is handed is what it reaches, which is the only thing it draws from."""
    answer = await client.post("/api/admin/signin", json={"login": "editor@acme.com", "password": "s3cret-password"})

    assert answer.status_code == 200
    assert "role" not in answer.json()["user"]

    reaches = await client.get("/api/meta/permissions", headers={"Authorization": f"Bearer {answer.json()['token']}"})

    assert set(reaches.json()["resources"]) == EDITED


async def test_the_panel_refuses_an_account_of_a_reader(client, db):
    await user_service.create(db, {"username": "outsider", "email": "outsider@acme.com", "password": "s3cret-password", "role": UserRole.NORMAL, "status": UserStatus.ACTIVE})

    answer = await client.post("/api/admin/signin", json={"login": "outsider@acme.com", "password": "s3cret-password"})

    assert answer.status_code == 401
    assert answer.json()["code"] == "error.panel-not-allowed"


async def test_what_an_account_reaches_is_what_its_role_was_given(client, editor_headers, admin_headers):
    editing = await client.get("/api/meta/permissions", headers=editor_headers)
    everything = await client.get("/api/meta/permissions", headers=admin_headers)

    assert set(editing.json()["resources"]) == EDITED
    assert set(everything.json()["resources"]) == set(RESOURCES)


async def test_an_account_never_reads_the_whole_map(client, member_headers):
    """A reader asking is answered about itself, and the shape of who reaches what is not a catalogue."""
    answer = await client.get("/api/meta/permissions", headers=member_headers)

    assert answer.json()["resources"] == []


async def test_the_map_is_not_answered_to_somebody_with_no_account(client):
    assert (await client.get("/api/meta/permissions")).status_code == 401


@pytest.mark.parametrize("resource", sorted(EDITED))
async def test_the_editor_reaches_what_it_was_given(client, editor_headers, resource):
    assert (await client.get(f"/api/{resource}", headers=editor_headers)).status_code == 200


@pytest.mark.parametrize("resource", sorted(set(RESOURCES) - EDITED))
async def test_the_editor_is_refused_everything_else(client, editor_headers, resource):
    """The line on the service is the whole of it, so what it does not name answers 403 without anybody writing that down."""
    assert (await client.get(f"/api/{resource}", headers=editor_headers)).status_code == 403


async def test_giving_a_resource_to_a_role_is_one_line(db, editor):
    """This is the property the whole thing rests on: what the factory guards a resource with is the line the service wrote."""
    from fastapi import FastAPI

    from helpers import errors
    from helpers.crud import build_readonly_router
    from schemas.commerce import ProductSchema
    from services.commerce import ProductService

    class OpenToEditors(ProductService):
        roles = (UserRole.ADMINISTRATOR, UserRole.EDITOR)

    application = FastAPI()
    errors.setup(application)
    application.include_router(build_readonly_router(OpenToEditors(), ProductSchema, "/widgets", "widgets"), prefix="/api")

    headers = {"Authorization": f"Bearer {create_token(editor.token, editor.role, editor.session_epoch)}"}

    async with AsyncClient(transport=ASGITransport(app=application), base_url="http://test") as caller:
        assert (await caller.get("/api/widgets", headers=headers)).status_code == 200


async def test_a_router_nobody_registered_is_in_no_permission(client, admin_headers, db, editor):
    """The registry says what this application serves, so a router built and never registered belongs to nothing."""
    from helpers.crud import RESOURCES, build_readonly_router
    from schemas.commerce import ProductSchema
    from services.commerce import ProductService

    build_readonly_router(ProductService(), ProductSchema, "/widgets", "widgets")

    assert "widgets" not in RESOURCES
    assert "widgets" not in (await client.get("/api/meta/permissions", headers=admin_headers)).json()["resources"]


def managed_paths() -> list[str]:
    """Every address that manages a resource the editor was never given, which is the whole surface it has to be refused."""
    from main import app
    from tests.test_role_matrix import ACCOUNT, OPEN

    withheld = set(RESOURCES) - EDITED
    named = {f"{method.upper()} {path}" for path, operations in app.openapi()["paths"].items() for method in operations if any(path.startswith(f"/api/{name}/") or path == f"/api/{name}" for name in withheld)}

    # A catalogue is an option of somebody else's form, and who resolves one is not who manages it.
    return sorted(name for name in named - OPEN - ACCOUNT if "/lookup" not in name)


@pytest.mark.parametrize("named", managed_paths())
async def test_the_editor_is_refused_every_address_of_what_it_was_not_given(client, editor_headers, named):
    """The router lets in whoever may resolve an option, so every route that is not one has to narrow again, and this is where that is proved."""
    method, path = named.split(" ", 1)
    filled = path.replace("{record_id}", "1").replace("{purpose}", "image").replace("{subscription_id}", "1").replace("{code}", "x").replace("{slug}", "x").replace("{tag}", "x").replace("{key}", "x").replace("{country_code}", "BR").replace("{purchase_id}", "1").replace("{address_type}", "main")

    answer = await client.request(method.upper(), filled, headers=editor_headers, json={} if method.upper() in ("POST", "PUT", "PATCH") else None)

    assert answer.status_code == 403, f"{named} answered {answer.status_code}"
