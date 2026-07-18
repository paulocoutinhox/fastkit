# fastkit-permissions

Permissions, roles, and authorization with a versioned cache.

## Model

A **role is the permission set** — there is no separate group. Permissions have a stable `code`
(e.g. `products.view`) checked by the authorizer.

## Authorizer

```python
authorizer = context.component("authorizer")
allowed = await authorizer.has_permission(user, "products.update")
```

- Checks `is_active` **before** the `is_root` short-circuit — a deactivated root is not authorized.
- `is_root` bypasses specific permission checks (the superuser).

## Tenant-scoped

`_role_ids_for_user` filters `UserRole` by `tenant_id == persisted OR tenant_id IS NULL` (global) — a
role assigned in one tenant never grants permissions in another. The permission cache's
`set(..., observed_version)` refuses to write if `bump_version()` ran during the compute await (no
stale re-cache).

## Idempotent grants

`grant_permission`/`assign_role` catch a duplicate `IntegrityError` and no-op (idempotent, never a
500). `set_role_permissions` de-dups its `permission_ids` and maps an `IntegrityError` (unknown
role/permission) to a 422 `FieldError`.

## The role editor router

Mount `build_role_router(runtime, security, manage_permission="roles.manage")` — a generic
role/permission editor. The `manage_permission` is a parameter with a sensible default. The admin
renders it via a `PermissionMatrixField` (see [Fields](../admin/fields.md)).
