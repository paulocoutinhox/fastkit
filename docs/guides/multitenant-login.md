# Multitenant login

FastKit is built so a single deployment serves many tenants that each log in differently (phone-only
here, email-only there, email/phone/cpf/username elsewhere). The consumer keeps full freedom over login
policy; the framework provides the generic, tenant-safe machinery.

## Any identifier type, extensible at runtime

Register a normalizer for your identifier type — it is immediately live in `identifier_types()`,
create/add-identifier, and login:

```python
def register_services(self, context):
    context.component("normalizer_registry").register(MyIdentifierNormalizer())
```

`default_registry()` ships email, username, phone, cpf, cnpj and social providers.

## Login is type-parameterized and tenant-scoped

```python
result = await auth_service.login(identifier_type="phone", identifier_value="+55…",
                                  password="…", requested_tenant_id=tenant_id)
```

`find_candidates(requested_tenant_id, type, value)` matches a `LoginIdentifier` only when
`tenant_id == persisted OR tenant_id IS NULL` (global) — the same value in tenant A never authenticates
into tenant B; a global identifier (root/staff) authenticates anywhere.

## Which methods a tenant offers is your policy

The login endpoint/form decides which `identifier_type`(s) to accept and render per tenant (see the
declarative login's method selector in [Customize the login screen](customize-login.md)). A tenant
naturally restricts its methods by which identifiers it issues (a phone-only tenant issues only phone
identifiers, so any other type simply finds no candidate). The framework deliberately does **not**
hardcode a per-tenant allowed-types table — a consumer that wants an explicit allow-list stores it (e.g.
on `Tenant.meta`) and enforces it at its own login endpoint.

## The admin is a global superadmin surface

The admin panel manages every tenant's data, gated by `is_staff`/`is_root`. Multitenancy lives in the
apps' end-user auth, not in the admin. See [Tenancy](../packages/tenancy.md) and
[Accounts](../packages/accounts.md).
