import pytest

from enums.user import UserRole, UserStatus
from services.user import user_service


async def test_sign_in_answers_a_token_and_the_account(client, member, tenant_headers):
    response = await client.post("/api/signin", json={"login": "reader", "password": "s3cret-password"}, headers=tenant_headers)

    assert response.status_code == 200
    assert response.json()["user"]["username"] == "reader"
    assert response.json()["token"]


@pytest.mark.parametrize("login", ["reader", "reader@acme.com"])
async def test_sign_in_accepts_every_login_identifier(client, member, tenant_headers, login):
    response = await client.post("/api/signin", json={"login": login, "password": "s3cret-password"}, headers=tenant_headers)

    assert response.status_code == 200


async def test_sign_in_by_cpf(client, db, tenant, tenant_headers):
    await user_service.create(db, {"username": "cpf-user", "cpf": "52998224725", "password": "s3cret-password", "tenant_id": tenant.id})

    response = await client.post("/api/signin", json={"login": "529.982.247-25", "password": "s3cret-password"}, headers=tenant_headers)

    assert response.status_code == 200


async def test_sign_in_refuses_a_wrong_password(client, member, tenant_headers):
    response = await client.post("/api/signin", json={"login": "reader", "password": "wrong-password"}, headers=tenant_headers)

    assert response.status_code == 401
    assert response.json()["code"] == "error.invalid-credentials"


async def test_sign_in_refuses_an_unknown_login(client, tenant, tenant_headers):
    response = await client.post("/api/signin", json={"login": "nobody", "password": "s3cret-password"}, headers=tenant_headers)

    assert response.status_code == 401


@pytest.mark.parametrize("status,code", [(UserStatus.BLOCKED, "error.account-blocked"), (UserStatus.PENDING, "error.account-pending")])
async def test_sign_in_refuses_an_unusable_account(client, db, member, tenant_headers, status, code):
    member.status = status
    await db.commit()

    response = await client.post("/api/signin", json={"login": "reader", "password": "s3cret-password"}, headers=tenant_headers)

    assert response.status_code == 401
    assert response.json()["code"] == code


async def test_admin_sign_in_accepts_an_administrator(client, administrator):
    response = await client.post("/api/admin/signin", json={"login": "root", "password": "s3cret-password"})

    assert response.status_code == 200
    assert response.json()["user"]["token"] == administrator.token
    assert "id" not in response.json()["user"]


async def test_admin_sign_in_refuses_a_normal_account(client, db):
    await user_service.create(db, {"username": "outsider", "password": "s3cret-password", "role": UserRole.NORMAL, "status": UserStatus.ACTIVE, "tenant_id": None})

    response = await client.post("/api/admin/signin", json={"login": "outsider", "password": "s3cret-password"})

    assert response.status_code == 401
    assert response.json()["code"] == "error.panel-not-allowed"


async def test_admin_sign_in_never_resolves_an_account_that_belongs_to_a_tenant(client, member):
    """An administrator is global, so a reader is not merely refused there, they are not found at all."""
    response = await client.post("/api/admin/signin", json={"login": "reader", "password": "s3cret-password"})

    assert response.status_code == 401
    assert response.json()["code"] == "error.invalid-credentials"


async def test_sign_up_creates_a_normal_account_of_the_header_tenant(client, tenant, tenant_headers):
    payload = {"username": "newcomer", "password": "s3cret-password", "email": "newcomer@acme.com"}

    response = await client.post("/api/signup", json=payload, headers=tenant_headers)

    assert response.status_code == 201
    assert response.json()["user"]["username"] == "newcomer"
    assert response.json()["user"]["token"]
    assert "id" not in response.json()["user"]


async def test_sign_up_refuses_a_login_already_in_use(client, member, tenant_headers):
    payload = {"username": "reader", "password": "s3cret-password", "email": "other@acme.com"}

    response = await client.post("/api/signup", json=payload, headers=tenant_headers)

    assert response.status_code == 409
    assert response.json()["errors"]["username"]


async def test_sign_up_takes_an_email_and_a_password_alone(client, tenant_headers):
    response = await client.post("/api/signup", json={"email": "reader@acme.com", "password": "s3cret-password"}, headers=tenant_headers)

    assert response.status_code == 201
    assert response.json()["user"]["email"] == "reader@acme.com"
    assert response.json()["user"]["username"] is None


async def test_sign_up_takes_a_username_and_a_password_alone(client, tenant_headers):
    response = await client.post("/api/signup", json={"username": "lonely", "password": "s3cret-password"}, headers=tenant_headers)

    assert response.status_code == 201
    assert response.json()["user"]["username"] == "lonely"


async def test_sign_up_needs_one_of_the_four_identities(client, tenant_headers):
    response = await client.post("/api/signup", json={"password": "s3cret-password"}, headers=tenant_headers)

    assert response.status_code == 422
    assert response.json()["code"] == "error.at-least-one-identity"


async def test_sign_up_refuses_an_invalid_cpf(client, tenant_headers):
    payload = {"username": "invalid", "password": "s3cret-password", "cpf": "12345678900"}

    response = await client.post("/api/signup", json=payload, headers=tenant_headers)

    assert response.status_code == 422
    assert "cpf" in response.json()["errors"]


async def test_sign_up_requires_a_known_tenant(client):
    payload = {"username": "newcomer", "password": "s3cret-password", "email": "newcomer@acme.com"}

    response = await client.post("/api/signup", json=payload, headers={"X-Tenant-Code": "unknown"})

    assert response.status_code == 400
    assert response.json()["code"] == "error.unknown-tenant"


async def test_sign_up_requires_the_tenant_header(client):
    payload = {"username": "newcomer", "password": "s3cret-password", "email": "newcomer@acme.com"}

    response = await client.post("/api/signup", json=payload)

    assert response.status_code == 422


async def test_sign_up_refuses_an_unknown_timezone(client, tenant_headers):
    payload = {"username": "newcomer", "password": "s3cret-password", "email": "newcomer@acme.com", "timezone": "Mars/Olympus"}

    response = await client.post("/api/signup", json=payload, headers=tenant_headers)

    assert response.status_code == 422
    assert "timezone" in response.json()["errors"]
