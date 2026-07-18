# Admin permissions

Every admin data endpoint and every rendered screen is permission-gated.

## Declaring permissions

```python
class ProductAdmin(AdminResource[Product]):
    permissions = {
        "list": "products.view", "detail": "products.view",
        "create": "products.create", "update": "products.update", "delete": "products.delete",
    }
```

Each action (`list`/`detail`/`create`/`update`/`delete`/custom action) checks its permission via the
runtime authorizer. Permission strings are entirely yours — the framework does not hardcode any.

## Screens are guarded too

The **server** guards each rendered screen: `dispatch_screen` calls `check_permission` for the
screen's action and renders `error.html` with status **403** on `AuthorizationError`, not a raw JSON
envelope. The toolbar only emits the New/Edit affordances when `flags.can_create`/`can_update`, so both
the buttons and the screens require permission.

The report screen is guarded the same way — a staff user lacking the report permission can't reach the
rendered report by URL even though the API already 403s.

## The audit hook

`AdminDeps.audit(action, resource_type, resource_id)` is called after create/update/delete. Wire it in
`build_admin_deps`:

```python
async def audit(action, resource_type, resource_id):
    await audit_service.record(action=action, resource_type=resource_type, resource_id=resource_id)

deps, security = build_admin_deps(runtime, audit=audit)
```

The actor comes from the [request context](../concepts/request-context.md) (set when the current user
resolves). The demo records create/update/delete plus login, logout and profile changes into
`AuditLog`, and exposes them through a `read_only` Activity log resource.

## The admin is a global superadmin surface

By design, the admin authorizes against a single configured `tenant_id` (`build_admin_deps(tenant_id=…)`,
default `0`/global) and does not scope its querysets per logged-in tenant — the `is_staff`/`is_root`
separation is the access boundary. Multitenancy lives in the apps' end-user auth. A consumer that needs
a per-tenant self-service panel wires its own security deps and `get_queryset()`.
