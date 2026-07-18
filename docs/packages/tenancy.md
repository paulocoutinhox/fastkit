# fastkit-tenancy

Multitenancy machinery: the `Tenant` model, tenant context, resolvers, and global-tenant semantics.

## Tenant model

`Tenant` (name, image_url, code, …) plus `TenantMixin` on any model that is tenant-scoped.

## Global-tenant semantics

`tenant_id = 0` ⇄ persisted `NULL`. A global tenant is used for root/staff and shared reference data,
and tenant-scoped uniqueness still holds for it via functional indexes over `coalesce(tenant_id, 0)`
(see [Conventions](../data/conventions.md)).

## Resolvers

Tenant resolvers determine the tenant for a request (for example from a subdomain). **Subdomain
resolution requires a real `.base_domain` boundary** — `notexample.com` is not a subdomain of
`example.com`.

## How tenancy is used

Multitenancy lives in the **apps' end-user auth** (per-tenant flexible login — see
[Accounts](accounts.md) and [Multitenant login](../guides/multitenant-login.md)), not in the admin.
The admin is a **global superadmin surface** gated by `is_staff`/`is_root` (a product decision) and
authorizes against a single configured `tenant_id` (default `0`). A consumer that needs a per-tenant
self-service panel wires its own security deps and `get_queryset()` (which can read
`get_request_context().tenant_id`).
