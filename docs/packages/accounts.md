# fastkit-accounts

Users, profiles, and **flexible, extensible login identifiers**.

## Identifiers and normalizers

A user can hold several **login identifiers** (email, phone, cpf, cnpj, username, social providers)
and log in by any of them. Each identifier type has a `LoginIdentifierNormalizer`
(`type`, `normalize`, `mask`, `validate`) held in a `NormalizerRegistry`. `default_registry()` ships
the built-ins.

The registry is a **shared component** (`normalizer_registry`), so a consumer registers its own type
at runtime and it is immediately live in `identifier_types()`, create/add-identifier, and login — no
framework change:

```python
def register_services(self, context):
    context.component("normalizer_registry").register(MyIdentifierNormalizer())
```

## AccountService

```python
accounts = context.component("account_service")
user = await accounts.create_user(tenant_id=0, identifiers=[("email", "a@b.com")],
                                  password_hash=hash, is_staff=True, is_root=True)
```

- `create_user` / `add_identifier` map a duplicate to `ConflictError`, not a raw 500.
- `update_profile` / `set_password_hash` raise `NotFound` for a missing user.
- Every identifier normalizer raises validation errors under `field="value"` (the form field), so the
  admin/profile forms display them correctly.

## Tenant-scoped, safe

`find_candidates(requested_tenant_id, type, value)` matches a `LoginIdentifier` only when
`tenant_id == persisted OR tenant_id IS NULL` (global). The same email in tenant A never authenticates
into tenant B; a global identifier (root/staff) authenticates anywhere. Uniqueness is the functional
index over `coalesce(tenant_id, 0), type, normalized_value`.

See [Multitenant login](../guides/multitenant-login.md) and [auth](auth.md).
