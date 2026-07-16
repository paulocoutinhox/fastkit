# fastkit-permissions

Roles, permissions and backend-authoritative authorization for FastKit.

## Installation

```bash
pip install fastkit-permissions
```

## Models

`Permission` (unique `code`, permission `group`, scope `global`/`tenant`/`own`/`custom`),
`Role`, `RolePermission` and `UserRole`. Roles are scoped per tenant.

A role *is* a named set of permissions, so there is no separate group concept: a
role is exactly what a group would be.

## Service

```python
perm = await permission_service.create_permission("users.update", "Update users", group="Users")
role = await permission_service.create_role("Editor", tenant_id=1)
await permission_service.grant_permission(role.id, perm.id)
await permission_service.assign_role(user.id, role.id, tenant_id=1)

# replace the whole permission set of a role at once (role editor)
await permission_service.set_role_permissions(role.id, [perm.id])
current = await permission_service.role_permission_ids(role.id)

# all permissions grouped by their permission group, for a grouped checkbox editor
groups = await permission_service.permissions_grouped()
```

A user's effective permissions come from their directly assigned roles.

## Authorization

```python
await authorizer.require(user, "users.update", tenant_id=1)
allowed = await authorizer.has_permission(user, "users.update", tenant_id=1)
```

- The database is the source of truth.
- `is_root` (admin) users bypass checks and hold every permission. Inactive users
  are always denied.
- Panel access is a separate policy the host enforces: a user may enter the admin
  panel when `is_staff` or `is_root` is set.
- The cache key includes user, tenant and a version that is bumped on every role
  change. A cache failure falls back to the database and a denial is never turned
  into an allow.

## Testing

100% branch coverage.

```bash
pytest packages/fastkit-permissions --cov=fastkit_permissions --cov-branch
```
