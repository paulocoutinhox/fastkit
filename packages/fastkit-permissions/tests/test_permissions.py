from types import SimpleNamespace

import pytest

from fastkit_core.errors.exceptions import AuthorizationError
from fastkit_permissions.cache import PermissionCache


async def _user(accounts, tenant_id=1, is_root=False):
    suffix = "root" if is_root else "staff"
    return await accounts.create_user(
        tenant_id=tenant_id,
        identifiers=[("email", f"{suffix}{id(object())}@acme.com")],
        is_root=is_root,
    )


async def test_direct_role_grants_permission(service, authorizer, accounts):
    user = await _user(accounts)
    permission = await service.create_permission("users.view", "View users")
    role = await service.create_role("Editor", tenant_id=1)

    await service.grant_permission(role.id, permission.id)
    await service.assign_role(user.id, role.id, tenant_id=1)

    assert await authorizer.has_permission(user, "users.view", tenant_id=1)
    await authorizer.require(user, "users.view", tenant_id=1)


async def test_duplicate_grant_and_assign_are_idempotent(service, accounts):
    user = await _user(accounts)
    permission = await service.create_permission("users.edit", "Edit users")
    role = await service.create_role("Manager", tenant_id=1)

    await service.grant_permission(role.id, permission.id)
    await service.grant_permission(role.id, permission.id)

    await service.assign_role(user.id, role.id, tenant_id=1)
    await service.assign_role(user.id, role.id, tenant_id=1)

    assert await service.role_permission_ids(role.id) == [permission.id]


async def test_tenant_scoped_role_does_not_leak_to_other_tenants(
    service, authorizer, accounts
):
    user = await _user(accounts)
    permission = await service.create_permission("users.view", "View users")
    role = await service.create_role("Editor", tenant_id=1)

    await service.grant_permission(role.id, permission.id)
    await service.assign_role(user.id, role.id, tenant_id=1)

    assert await authorizer.has_permission(user, "users.view", tenant_id=1)
    assert not await authorizer.has_permission(user, "users.view", tenant_id=2)
    assert not await authorizer.has_permission(user, "users.view", tenant_id=0)


async def test_global_role_applies_in_every_tenant(service, authorizer, accounts):
    user = await _user(accounts)
    permission = await service.create_permission("users.view", "View users")
    role = await service.create_role("GlobalEditor", tenant_id=0)

    await service.grant_permission(role.id, permission.id)
    await service.assign_role(user.id, role.id, tenant_id=0)

    assert await authorizer.has_permission(user, "users.view", tenant_id=0)
    assert await authorizer.has_permission(user, "users.view", tenant_id=7)


async def test_missing_permission_denied(service, authorizer, accounts):
    user = await _user(accounts)

    assert not await authorizer.has_permission(user, "users.delete", tenant_id=1)

    with pytest.raises(AuthorizationError, match="users.delete"):
        await authorizer.require(user, "users.delete", tenant_id=1)


async def test_root_bypasses_checks(authorizer, accounts):
    root = await _user(accounts, tenant_id=0, is_root=True)

    assert await authorizer.has_permission(root, "anything.at.all", tenant_id=5)


async def test_inactive_user_has_no_permissions(authorizer):
    user = SimpleNamespace(id="x", is_root=False, is_active=False)

    assert not await authorizer.has_permission(user, "users.view", tenant_id=1)


async def test_cache_is_used_and_invalidated(service, authorizer, accounts, cache):
    user = await _user(accounts)
    permission = await service.create_permission("reports.export", "Export")
    role = await service.create_role("Analyst", tenant_id=1)
    await service.grant_permission(role.id, permission.id)
    await service.assign_role(user.id, role.id, tenant_id=1)

    first = await authorizer.permissions_for(user, tenant_id=1)
    assert cache.get(user.id, 1) == first
    assert "reports.export" in first

    version_before = cache.version
    await service.assign_role(user.id, role.id, tenant_id=2)
    assert cache.version > version_before
    assert cache.get(user.id, 1) is None


async def test_authorizer_without_cache(service, accounts):
    from fastkit_permissions.authorization import Authorizer

    user = await _user(accounts)
    no_cache = Authorizer(service, cache=None)

    assert await no_cache.permissions_for(user, tenant_id=1) == set()


async def test_cache_read_failure_falls_back_to_database(service, accounts):
    from fastkit_permissions.authorization import Authorizer

    class BrokenCache:
        version = 1

        def get(self, user_id, tenant_id):
            raise RuntimeError("cache down")

        def set(self, user_id, tenant_id, permissions, observed_version):
            raise RuntimeError("cache down")

    user = await _user(accounts)
    authorizer = Authorizer(service, cache=BrokenCache())

    assert await authorizer.permissions_for(user, tenant_id=1) == set()


async def test_service_without_cache_still_assigns(database, accounts):
    from fastkit_permissions.authorization import Authorizer
    from fastkit_permissions.service import PermissionService

    service = PermissionService(database, cache=None)
    user = await _user(accounts)
    permission = await service.create_permission("cache.clear", "Clear cache")
    role = await service.create_role("Ops", tenant_id=1)

    await service.grant_permission(role.id, permission.id)
    await service.assign_role(user.id, role.id, tenant_id=1)

    assert await Authorizer(service).has_permission(user, "cache.clear", tenant_id=1)

    await service.set_role_permissions(role.id, [permission.id])
    assert set(await service.role_permission_ids(role.id)) == {permission.id}


async def test_set_role_permissions_dedups_and_rejects_unknown_ids(service):
    from fastkit_core.errors.exceptions import ValidationError

    permission = await service.create_permission("orders.view", "View orders")
    role = await service.create_role("Sales", tenant_id=1)

    await service.set_role_permissions(role.id, [permission.id, permission.id])
    assert await service.role_permission_ids(role.id) == [permission.id]

    with pytest.raises(ValidationError):
        await service.set_role_permissions(role.id, [999999])


async def test_permissions_grouped(service):
    await service.create_permission("users.view", "View users", group="Users")
    await service.create_permission("users.create", "Create users", group="Users")
    await service.create_permission("reports.export", "Export reports", group="Reports")

    grouped = await service.permissions_grouped()
    by_group = {entry["group"]: entry["permissions"] for entry in grouped}

    assert {"Users", "Reports"} <= set(by_group)
    assert len(by_group["Users"]) == 2
    assert by_group["Reports"][0]["code"] == "reports.export"


async def test_set_role_permissions_replaces(service, authorizer, accounts):
    user = await _user(accounts)
    view = await service.create_permission("users.view", "View", group="Users")
    edit = await service.create_permission("users.update", "Update", group="Users")
    role = await service.create_role("Editor", tenant_id=1)
    await service.assign_role(user.id, role.id, tenant_id=1)

    await service.set_role_permissions(role.id, [view.id, edit.id])
    assert await service.role_permission_ids(role.id) == [view.id, edit.id] or set(
        await service.role_permission_ids(role.id)
    ) == {view.id, edit.id}

    await service.set_role_permissions(role.id, [view.id])
    assert set(await service.role_permission_ids(role.id)) == {view.id}

    await service.set_role_permissions(role.id, [])
    assert await service.role_permission_ids(role.id) == []


async def test_deleting_role_cascades(service, database, accounts):
    from fastkit_permissions.models import RolePermission, UserRole, Role
    from sqlalchemy import select

    user = await _user(accounts)
    permission = await service.create_permission("x.y", "XY", group="G")
    role = await service.create_role("Temp", tenant_id=1)
    await service.grant_permission(role.id, permission.id)
    await service.assign_role(user.id, role.id, tenant_id=1)

    async with database.session_factory() as session:
        stored = await session.get(Role, role.id)
        await session.delete(stored)
        await session.commit()

    async with database.session_factory() as session:
        role_permissions = (
            (await session.execute(select(RolePermission))).scalars().all()
        )
        user_roles = (await session.execute(select(UserRole))).scalars().all()

    assert role_permissions == []
    assert user_roles == []


def test_permission_cache_versioning():
    cache = PermissionCache()
    cache.set("u1", 1, {"a"}, cache.version)

    assert cache.get("u1", 1) == {"a"}

    cache.bump_version()
    assert cache.get("u1", 1) is None


def test_permission_cache_rejects_stale_write_after_bump():
    cache = PermissionCache()
    observed = cache.version
    cache.bump_version()
    cache.set("u1", 1, {"stale"}, observed)

    assert cache.get("u1", 1) is None


def test_role_display_label():
    from fastkit_permissions.models import Role

    assert Role(name="Administrator").display_label() == "Administrator"
