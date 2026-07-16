# fastkit-tenancy

Multi-tenancy for FastKit: the `Tenant` model, a request-scoped tenant context,
pluggable resolvers and the global-tenant semantics.

The `Tenant` model carries a `name` and an optional `image_url` alongside its
`code`, `status`, `default_locale`, `timezone` and `domain`, so a host can build
per-tenant branded screens.

## Installation

```bash
pip install fastkit-tenancy
```

## Global tenant

The platform scope is exposed publicly as `tenant_id = 0` and may be persisted as
`NULL` for portability. Conversions keep both worlds consistent:

```python
from fastkit_tenancy.constants import to_persisted, to_api, is_global

to_persisted(0)   # -> None
to_api(None)      # -> 0
```

## Context

`TenantContext` carries `requested_tenant_id`, `effective_tenant_id`, `source`
and `resolved_at`. It lives in a `ContextVar`, never a mutable global.
`require_tenant_context` fails when a tenant-scoped operation runs without one.

## Resolvers

`SubdomainTenantResolver`, `HeaderTenantResolver`, `PathTenantResolver` and
`ExplicitTenantResolver` each return a tenant code or `None`. A
`TenantResolverChain` runs them in configured order and returns the first match.

## Service rules

- `TenantService.require_active` loads an active tenant or raises `tenant.*`.
- `assert_access` blocks a tenant-local identity from acting on another tenant.
- `resolve_effective_tenant` lets a global identity adopt the requested tenant
  while a tenant-local identity keeps its own.

## Testing

100% branch coverage.

```bash
pytest packages/fastkit-tenancy --cov=fastkit_tenancy --cov-branch
```
