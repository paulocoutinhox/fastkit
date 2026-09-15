import pytest

from enums.user import UserRole, UserStatus
from services.user import user_service
from tests.factories import make_tenant


async def test_sign_in_answers_a_token_and_the_account(client, member, tenant_headers):
    response = await client.post("/api/signin", json={"login": "reader", "password": "s3cret-password"}, headers=tenant_headers)

    assert response.status_code == 200
    assert response.json()["user"]["username"] == "reader"
    assert response.json()["token"]


@pytest.mark.parametrize("login", ["reader", "reader@acme.com"])
async def test_sign_in_accepts_every_login_identifier(client, member, tenant_headers, login):
    response = await client.post("/api/signin", json={"login": login, "password": "s3cret-password"}, headers=tenant_headers)

    assert response.status_code == 200


async def test_sign_in_by_document(client, db, tenant, tenant_headers):
    await user_service.create(db, {"username": "document-user", "document": "52998224725", "password": "s3cret-password", "tenant_id": tenant.id})

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


async def test_a_reader_of_the_brand_the_panel_was_opened_on_is_found_and_refused_by_role(client, member):
    """The panel resolves its brand like the site, so the reader is found there and turned away for what they are, not for who they are."""
    response = await client.post("/api/admin/signin", json={"login": "reader", "password": "s3cret-password"}, headers={"host": member.tenant.domain})

    assert response.status_code == 401
    assert response.json()["code"] == "error.panel-not-allowed"


async def operator(db, tenant, username: str):
    return await user_service.create(db, {"username": username, "password": "s3cret-password", "role": UserRole.EDITOR, "status": UserStatus.ACTIVE, "tenant_id": tenant.id if tenant else None})


async def test_an_operator_of_a_brand_signs_in_on_the_domain_of_that_brand(client, db, tenant):
    """Confining an operator to a brand is worth nothing if the panel never lets that operator in."""
    keeper = await operator(db, tenant, "keeper")

    response = await client.post("/api/admin/signin", json={"login": "keeper", "password": "s3cret-password"}, headers={"host": tenant.domain})

    assert response.status_code == 200
    assert response.json()["user"]["token"] == keeper.token


async def test_an_operator_of_a_brand_is_not_found_on_the_domain_of_another(client, db, tenant):
    other = await make_tenant(db, code="rival", domain="rival.acme.com")
    await operator(db, tenant, "keeper")

    response = await client.post("/api/admin/signin", json={"login": "keeper", "password": "s3cret-password"}, headers={"host": other.domain})

    assert response.status_code == 401
    assert response.json()["code"] == "error.invalid-credentials"


async def test_an_operator_of_no_brand_signs_in_on_the_domain_of_any(client, administrator, tenant):
    response = await client.post("/api/admin/signin", json={"login": "root", "password": "s3cret-password"}, headers={"host": tenant.domain})

    assert response.status_code == 200
    assert response.json()["user"]["token"] == administrator.token


async def test_the_brand_own_operator_answers_when_one_of_no_brand_shares_the_login(client, db, administrator, tenant):
    own = await operator(db, tenant, "root")

    response = await client.post("/api/admin/signin", json={"login": "root", "password": "s3cret-password"}, headers={"host": tenant.domain})

    assert response.status_code == 200
    assert response.json()["user"]["token"] == own.token


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


async def test_sign_up_refuses_an_invalid_document(client, tenant_headers):
    payload = {"username": "invalid", "password": "s3cret-password", "document": "12345678900"}

    response = await client.post("/api/signup", json=payload, headers=tenant_headers)

    assert response.status_code == 422
    assert "document" in response.json()["errors"]


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


async def test_an_operator_of_no_brand_signs_in_on_a_brand_where_a_customer_shares_the_login(client, db, tenant):
    """A customer of the brand with the same address is no operator, so the panel finds the one who is, and never counts the customer's lockout."""
    root = await operator(db, None, "keeper")
    customer = await user_service.create(db, {"username": "keeper", "password": "another-password", "tenant_id": tenant.id})

    response = await client.post("/api/admin/signin", json={"login": "keeper", "password": "s3cret-password"}, headers={"host": tenant.domain})

    assert response.status_code == 200
    assert response.json()["user"]["token"] == root.token
    assert (await db.get(type(customer), customer.id, populate_existing=True)).failed_sign_ins == 0


async def test_an_account_the_api_signs_up_reads_in_the_language_it_was_written_in(client, db, tenant_headers):
    from tests.factories import make_language

    portuguese = await make_language(db, name="Portuguese", native_name="Português", code_iso_639_1="pt", code_iso_language="pt-br")

    response = await client.post("/api/signup", json={"username": "leitora", "password": "s3cret-password"}, headers={**tenant_headers, "Accept-Language": "pt"})

    assert response.status_code == 201
    assert response.json()["user"]["languageId"] == portuguese.id
