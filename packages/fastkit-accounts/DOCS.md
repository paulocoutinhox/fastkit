# fastkit-accounts

Users, profiles and login identifiers for FastKit, with pluggable identifier
normalizers.

## Installation

```bash
pip install fastkit-accounts
```

## Models

- `User` — generic account with `is_active`, `is_staff`, `is_root`, `is_verified`,
  locale, timezone, login counters and lockout. `password_hash` is set by
  `fastkit-auth` and never exposed in output schemas.
- `UserProfile` — one-to-one profile with avatar and bio.
- `LoginIdentifier` — supports many formats per user. Unique per
  `(tenant_id, type, normalized_value)`.

## Normalizers

Each identifier type has a normalizer that trims, normalizes and validates:
`EmailNormalizer` (NFKC + lowercase), `UsernameNormalizer`, `PhoneNormalizer`
(E.164), `CpfNormalizer` (digits only). Register your own for `external`/`custom`
types through `NormalizerRegistry`.

## Service

```python
user = await account_service.create_user(
    tenant_id=1,
    identifiers=[("email", "owner@acme.com"), ("username", "owner")],
    is_staff=True,
)

candidates = await account_service.find_candidates(1, "email", "owner@acme.com")
```

- The same identifier value is unique inside a tenant but may repeat across
  tenants.
- `find_candidates` returns both the tenant-local and the global matches, without
  revealing which exists, for the auth flow to resolve.
- `is_root=True` is only accepted for the global tenant.

## Testing

100% branch coverage.

```bash
pytest packages/fastkit-accounts --cov=fastkit_accounts --cov-branch
```
