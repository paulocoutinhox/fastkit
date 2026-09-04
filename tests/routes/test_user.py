import pytest

from enums.account import CreditTransactionType
from enums.user import UserRole
from helpers.security import verify_password
from services.account import credit_transaction_service
from services.user import user_service
from tests.factories import make_language, make_tenant


def build_payload(**overrides) -> dict:
    return {"username": "newcomer", "email": "newcomer@acme.com", "password": "s3cret-password"} | overrides


async def test_create_stores_a_hashed_password(client, db, admin_headers):
    response = await client.post("/api/users", json=build_payload(), headers=admin_headers)

    assert response.status_code == 201
    assert "password" not in response.json()

    user = await user_service.get(db, response.json()["id"])

    assert user.password_hash != "s3cret-password"
    assert await verify_password("s3cret-password", user.password_hash) is True


async def test_create_normalizes_the_email_and_the_cpf(client, admin_headers):
    response = await client.post("/api/users", json=build_payload(email="MiXeD@Acme.com", cpf="529.982.247-25"), headers=admin_headers)

    assert response.json()["email"] == "mixed@acme.com"
    assert response.json()["cpf"] == "52998224725"


@pytest.mark.parametrize("field,value,code", [("username", "reader", "error.username-already-used"), ("email", "reader@acme.com", "error.email-already-used")])
async def test_create_refuses_a_login_already_in_use_inside_the_same_tenant(client, member, admin_headers, field, value, code):
    response = await client.post("/api/users", json=build_payload(tenantId=member.tenant_id, **{field: value}), headers=admin_headers)

    assert response.status_code == 409
    assert response.json()["code"] == code


@pytest.mark.parametrize("field,value", [("username", "reader"), ("email", "reader@acme.com")])
async def test_the_same_identity_belongs_to_one_person_in_each_tenant(client, db, member, admin_headers, field, value):
    other = await make_tenant(db, code="other", name="Other")

    response = await client.post("/api/users", json=build_payload(tenantId=other.id, **{field: value}), headers=admin_headers)

    assert response.status_code == 201


@pytest.mark.parametrize("field,value,code", [("username", "keeper", "error.username-already-used"), ("email", "keeper@acme.com", "error.email-already-used")])
async def test_two_accounts_outside_every_tenant_still_share_one_scope(client, db, admin_headers, field, value, code):
    """No null equals another, so a plain unique index would let a second global account through."""
    await user_service.create(db, {"username": "keeper", "email": "keeper@acme.com", "password": "s3cret-password", "tenant_id": None})

    response = await client.post("/api/users", json=build_payload(**{field: value}), headers=admin_headers)

    assert response.status_code == 409
    assert response.json()["code"] == code


async def test_create_takes_a_username_alone(client, admin_headers):
    response = await client.post("/api/users", json={"username": "lonely", "password": "s3cret-password"}, headers=admin_headers)

    assert response.status_code == 201


async def test_create_needs_one_of_the_four_identities(client, admin_headers):
    response = await client.post("/api/users", json={"password": "s3cret-password"}, headers=admin_headers)

    assert response.status_code == 422
    assert response.json()["code"] == "error.at-least-one-identity"


async def test_create_refuses_a_short_password(client, admin_headers):
    response = await client.post("/api/users", json=build_payload(password="short"), headers=admin_headers)

    assert response.status_code == 422
    assert "password" in response.json()["errors"]


async def test_update_changes_the_password_when_it_is_sent(client, db, member, admin_headers):
    response = await client.put(f"/api/users/{member.id}", json={"password": "another-password"}, headers=admin_headers)

    assert response.status_code == 200

    await db.refresh(member)

    assert await verify_password("another-password", member.password_hash) is True


async def test_update_keeps_the_password_when_it_is_absent(client, db, member, admin_headers):
    previous = member.password_hash

    await client.put(f"/api/users/{member.id}", json={"firstName": "Ada"}, headers=admin_headers)
    await db.refresh(member)

    assert member.password_hash == previous


async def test_update_keeps_an_account_that_still_has_a_username(client, member, admin_headers):
    response = await client.put(f"/api/users/{member.id}", json={"email": None}, headers=admin_headers)

    assert response.status_code == 200
    assert response.json()["email"] is None


async def test_update_refuses_clearing_every_identity(client, member, admin_headers):
    response = await client.put(f"/api/users/{member.id}", json={"username": None, "email": None, "cpf": None, "mobilePhone": None}, headers=admin_headers)

    assert response.status_code == 422
    assert response.json()["code"] == "error.at-least-one-identity"


async def test_update_promotes_to_administrator(client, member, admin_headers):
    response = await client.put(f"/api/users/{member.id}", json={"role": UserRole.ADMINISTRATOR}, headers=admin_headers)

    assert response.json()["role"] == UserRole.ADMINISTRATOR


async def test_delete_removes_the_account(client, member, admin_headers):
    assert (await client.delete(f"/api/users/{member.id}", headers=admin_headers)).status_code == 204
    assert (await client.get(f"/api/users/{member.id}", headers=admin_headers)).status_code == 404


async def test_relations_are_answered_expanded(client, db, member, admin_headers):
    language = await make_language(db)

    await client.put(f"/api/users/{member.id}", json={"languageId": language.id}, headers=admin_headers)

    response = await client.get(f"/api/users/{member.id}", headers=admin_headers)

    assert response.json()["language"]["codeIso6391"] == "en"
    assert response.json()["tenant"]["code"] == "acme"


async def test_filter_by_role_and_status(client, member, administrator, admin_headers):
    assert (await client.get("/api/users?role=normal", headers=admin_headers)).json()["count"] == 1
    assert (await client.get("/api/users?role=administrator", headers=admin_headers)).json()["count"] == 1
    assert (await client.get("/api/users?status=active", headers=admin_headers)).json()["count"] == 2


async def test_an_ordering_the_list_does_not_answer_is_refused(client, member, administrator, admin_headers):
    """Falling back to the default answered a different order than the one asked for, and the caller had no way to see it."""
    response = await client.get("/api/users?ordering=whatever", headers=admin_headers)

    assert response.status_code == 422
    assert response.json()["errors"] == {"ordering": response.json()["detail"]}


async def test_ordering_ascending_by_username(client, member, administrator, admin_headers):
    response = await client.get("/api/users?ordering=username", headers=admin_headers)

    assert [item["username"] for item in response.json()["items"]] == ["reader", "root"]


async def test_a_balance_is_not_something_the_account_payload_can_move(client, member, admin_headers):
    """The balance is the running total of a ledger, and a hand written one would stop matching its own history."""
    assert (await client.put(f"/api/users/{member.id}", json={"amount": 999}, headers=admin_headers)).status_code == 422
    assert (await client.post("/api/users", json={"username": "rich", "password": "s3cret-password", "amount": 500}, headers=admin_headers)).status_code == 422


async def test_the_balance_is_answered_on_a_surface_of_its_own(client, db, member, currency, admin_headers):
    """The account holds as many balances as the product has currencies, so it is a list of its own and never a column of the account."""
    await credit_transaction_service.move(db, member.id, currency.id, CreditTransactionType.CREDIT, 40, None, "opening", None, {})

    listed = (await client.get(f"/api/user-balances?userId={member.id}", headers=admin_headers)).json()

    assert [(row["currency"]["code"], row["amount"]) for row in listed["items"]] == [("coin", 40)]


async def test_an_operator_fixes_the_address_a_customer_cannot_reach(client, db, member, country, admin_headers):
    """An admin edits the account, and an address it cannot edit is a support call that ends in a SQL console."""
    created = await client.post("/api/user-addresses", json={"userId": member.id, "type": "main", "line1": "221B Baker Street", "city": "London", "state": "London", "postalCode": "NW16XE", "countryCode": "gb"}, headers=admin_headers)

    assert created.status_code == 201
    assert created.json()["countryCode"] == "GB"

    changed = await client.put(f"/api/user-addresses/{created.json()['id']}", json={"city": "Bristol"}, headers=admin_headers)

    assert changed.status_code == 200
    assert changed.json()["city"] == "Bristol"


async def test_one_address_per_purpose_is_still_the_rule_when_an_operator_writes_it(client, db, member, country, admin_headers):
    payload = {"userId": member.id, "type": "main", "line1": "221B Baker Street", "city": "London", "state": "London", "postalCode": "NW16XE", "countryCode": "GB"}

    assert (await client.post("/api/user-addresses", json=payload, headers=admin_headers)).status_code == 201

    refused = await client.post("/api/user-addresses", json=payload, headers=admin_headers)

    assert refused.status_code == 409
    assert refused.json()["code"] == "error.address-type-already-used"
