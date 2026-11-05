from enums.user_role import UserRole
from enums.user_status import UserStatus
from helpers.security import create_token
from models.user_group import UserGroup
from models.user_group_member import UserGroupMember
from services.user_group_service import user_group_service
from services.user_service import user_service
from tests.factories import make_tenant, save


async def test_a_group_derives_its_code_from_the_name(client, admin_headers):
    response = await client.post("/api/user-groups", json={"name": "Finance Team"}, headers=admin_headers)

    assert response.status_code == 201
    assert response.json()["code"] == "finance-team"


async def test_a_code_is_unique_inside_a_brand_and_free_in_another(client, db, tenant, admin_headers):
    other = await make_tenant(db, code="other", domain="other.test")

    await client.post("/api/user-groups", json={"name": "Finance", "tenantId": tenant.id}, headers=admin_headers)

    repeated = await client.post("/api/user-groups", json={"name": "Finance", "tenantId": tenant.id}, headers=admin_headers)
    elsewhere = await client.post("/api/user-groups", json={"name": "Finance", "tenantId": other.id}, headers=admin_headers)

    assert repeated.status_code == 409
    assert repeated.json()["errors"]["code"]
    assert elsewhere.status_code == 201


async def test_a_group_of_no_brand_never_takes_a_code_some_brand_already_named(client, db, tenant, admin_headers):
    await save(db, UserGroup(code="finance", name="Finance", tenant_id=tenant.id))

    answer = await client.post("/api/user-groups", json={"name": "Finance"}, headers=admin_headers)

    assert answer.status_code == 409


async def test_a_group_moved_out_of_its_brand_never_takes_a_code_another_brand_named(client, db, tenant, admin_headers):
    other = await make_tenant(db, code="other", domain="other.test")
    await save(db, UserGroup(code="vip", name="VIP", tenant_id=other.id))
    moved = await save(db, UserGroup(code="vip", name="VIP", tenant_id=tenant.id))

    answer = await client.put(f"/api/user-groups/{moved.id}", json={"tenantId": None}, headers=admin_headers)

    assert answer.status_code == 409
    assert answer.json()["errors"]["code"]


async def test_a_group_of_one_brand_refuses_an_account_of_another(client, db, tenant, member, admin_headers):
    other = await make_tenant(db, code="other", domain="other.test")
    group = await save(db, UserGroup(code="finance", name="Finance", tenant_id=other.id))

    response = await client.post("/api/user-group-members", json={"groupId": group.id, "userId": member.id}, headers=admin_headers)

    assert response.status_code == 422
    assert response.json()["code"] == "error.member-of-another-brand"


async def test_a_group_of_no_brand_holds_an_account_of_any_brand(client, db, member, admin_headers):
    group = await save(db, UserGroup(code="finance", name="Finance"))

    response = await client.post("/api/user-group-members", json={"groupId": group.id, "userId": member.id}, headers=admin_headers)

    assert response.status_code == 201
    assert response.json()["user"]["displayName"]
    assert await user_group_service.codes_of(db, member) == {"finance"}


async def test_an_account_belongs_to_a_group_once(client, db, member, admin_headers):
    group = await save(db, UserGroup(code="finance", name="Finance"))
    payload = {"groupId": group.id, "userId": member.id}

    await client.post("/api/user-group-members", json=payload, headers=admin_headers)
    repeated = await client.post("/api/user-group-members", json=payload, headers=admin_headers)

    assert repeated.status_code == 409


async def test_deleting_a_group_takes_its_memberships(client, db, member, admin_headers):
    group = await save(db, UserGroup(code="finance", name="Finance"))
    await save(db, UserGroupMember(group_id=group.id, user_id=member.id))

    response = await client.delete(f"/api/user-groups/{group.id}", headers=admin_headers)

    assert response.status_code == 204
    assert await user_group_service.codes_of(db, member) == frozenset()


async def test_an_erased_account_leaves_every_group_it_was_in(db, member):
    group = await save(db, UserGroup(code="finance", name="Finance"))
    await save(db, UserGroupMember(group_id=group.id, user_id=member.id))

    await user_service.erase(db, member)

    assert await user_group_service.codes_of(db, member) == frozenset()


async def test_an_operator_of_a_brand_manages_the_groups_of_that_brand_alone(client, db, tenant):
    operator = await user_service.create(db, {"username": "brandadmin", "email": "brandadmin@acme.com", "password": "s3cret-password", "role": UserRole.ADMINISTRATOR, "status": UserStatus.ACTIVE, "tenant_id": tenant.id})
    other = await make_tenant(db, code="other", domain="other.test")
    await save(db, UserGroup(code="finance", name="Finance", tenant_id=other.id))
    await save(db, UserGroup(code="global", name="Global"))

    headers = {"Authorization": f"Bearer {create_token(operator.token, operator.role, operator.session_epoch)}"}
    created = await client.post("/api/user-groups", json={"name": "Sales", "tenantId": other.id}, headers=headers)
    listed = await client.get("/api/user-groups", headers=headers)

    assert created.json()["tenantId"] == tenant.id
    assert [group["code"] for group in listed.json()["items"]] == ["sales"]
