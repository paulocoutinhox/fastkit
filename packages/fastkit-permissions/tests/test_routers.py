from types import SimpleNamespace

from fastkit_permissions.routers import RolePermissions, build_role_router


class _PermissionService:
    def __init__(self):
        self.saved = None

    async def permissions_grouped(self):
        return [{"group": "General", "permissions": []}]

    async def role_permission_ids(self, role_id):
        return [1, 2]

    async def set_role_permissions(self, role_id, permission_ids):
        self.saved = (role_id, permission_ids)


class _Security:
    def __init__(self):
        self.checks = []

    async def get_current_user(self):
        return SimpleNamespace(id=1)

    async def authorize(self, user, permission):
        self.checks.append(permission)


def _endpoints(runtime, security, **kwargs):
    router = build_role_router(runtime, security, **kwargs)

    return {
        (route.path, tuple(sorted(route.methods))): route.endpoint
        for route in router.routes
    }


def _runtime(service):
    return SimpleNamespace(component=lambda name: service)


async def test_grouped_permissions_requires_and_returns():
    service = _PermissionService()
    security = _Security()
    endpoints = _endpoints(_runtime(service), security)

    result = await endpoints[("/meta/permissions", ("GET",))](
        user=SimpleNamespace(id=1)
    )

    assert result["data"] == [{"group": "General", "permissions": []}]
    assert security.checks == ["roles.manage"]


async def test_role_permissions_serializes_ids():
    endpoints = _endpoints(_runtime(_PermissionService()), _Security())

    result = await endpoints[("/roles/{role_id}/permissions", ("GET",))](
        role_id=5, user=SimpleNamespace(id=1)
    )

    assert result["data"] == {"permission_ids": ["1", "2"]}


async def test_set_role_permissions_saves_with_custom_permission():
    service = _PermissionService()
    security = _Security()
    endpoints = _endpoints(_runtime(service), security, manage_permission="acl.edit")
    endpoint = endpoints[("/roles/{role_id}/permissions", ("PUT",))]

    result = await endpoint(
        role_id=9,
        payload=RolePermissions(permission_ids=[3, 4]),
        user=SimpleNamespace(id=1),
    )

    assert service.saved == (9, [3, 4])
    assert security.checks == ["acl.edit"]
    assert result["message"]["code"] == "roles.permissions_updated"
