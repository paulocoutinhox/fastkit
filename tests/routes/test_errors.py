import pytest
from fastapi import APIRouter, FastAPI
from httpx import ASGITransport, AsyncClient

from helpers import errors, locale
from helpers.errors import AppError, ConflictError, NotFoundError, PermissionError, field_path


@pytest.fixture
def broken_app():
    application = FastAPI()
    router = APIRouter()

    @router.get("/boom")
    async def boom():
        raise RuntimeError("unexpected")

    @router.get("/known")
    async def known():
        raise NotFoundError()

    locale.setup(application)
    errors.setup(application)
    application.include_router(router)

    return application


@pytest.fixture
async def broken_client(broken_app):
    async with AsyncClient(transport=ASGITransport(app=broken_app, raise_app_exceptions=False), base_url="http://test") as instance:
        yield instance


async def test_an_unexpected_error_answers_a_translated_payload(broken_client):
    response = await broken_client.get("/boom")

    assert response.status_code == 500
    assert response.json() == {"code": "error.internal", "detail": "Something went wrong on our side.", "errors": {}}


async def test_a_domain_error_answers_its_own_code(broken_client):
    response = await broken_client.get("/known")

    assert response.status_code == 404
    assert response.json()["code"] == "error.not-found"


async def test_an_unknown_path_answers_a_translated_not_found(client):
    response = await client.get("/api/does-not-exist")

    assert response.status_code == 404
    assert response.json()["code"] == "error.not-found"


async def test_a_wrong_method_answers_a_translated_message(client, admin_headers):
    response = await client.patch("/api/tenants", headers=admin_headers)

    assert response.status_code == 405
    assert response.json()["code"] == "error.method-not-allowed"


async def test_messages_follow_the_accept_language_header(client, tenant_headers):
    headers = {**tenant_headers, "Accept-Language": "pt-BR,pt;q=0.9"}

    response = await client.post("/api/signup", json={"username": "ab", "password": "s3cret-password", "email": "a@acme.com"}, headers=headers)

    assert response.status_code == 422
    assert response.json()["detail"] == "Alguns campos precisam da sua atenção."


async def test_messages_default_to_english(client, tenant_headers):
    response = await client.post("/api/signup", json={"username": "ab", "password": "s3cret-password", "email": "a@acme.com"}, headers=tenant_headers)

    assert response.json()["detail"] == "Some fields need your attention."


async def test_an_unknown_field_is_refused(client, admin_headers):
    response = await client.post("/api/tenants", json={"name": "X", "domain": "x.example.org", "whatever": 1}, headers=admin_headers)

    assert response.status_code == 422
    assert response.json()["errors"]["whatever"] == "This field is not accepted."


def test_field_path_drops_the_request_part():
    assert field_path(("body", "email")) == "email"
    assert field_path(("body", "events", 0, "uuid")) == "events.0.uuid"
    assert field_path(("body",)) == "body"


def test_app_error_carries_its_translated_message():
    assert AppError("error.not-found").message == "The requested record was not found."
    assert ConflictError("error.code-already-used", "code").status_code == 409
    assert PermissionError().status_code == 403
