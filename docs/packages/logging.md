# fastkit-logging

Structured logging plus persisted `SystemLog` and `AuditLog`, with sanitization.

## Models

- **`SystemLog`** — application events with a `category`, `event`, `level`, `message` and payload.
- **`AuditLog`** — who did what to which record (the admin records create/update/delete + login,
  logout, profile changes here).

## Services

```python
system_logs = context.component("system_log_service")
await system_logs.record(level="warning", category="auth", event="login_failed",
                         message="bad password", payload={"ip": ip})
```

`SystemLogService.record` resolves the log level by name (`logging.getLevelName`), so a lowercase
level (`warning`) logs at the correct level instead of raising `TypeError`.

The actor (`user_id`) and `tenant_id` come from the [request context](../concepts/request-context.md),
so audit rows record the real actor and tenant.

## Sanitization

`logging.sanitize` redacts secret keys by **specific markers** (`api_key`/`bearer`/`cvv`/`ssn`/
`card_number`/…) — never an over-broad `card` that would hide `wildcard` — and redacts a whole
container past its depth cap so a deep-nested secret can't leak through.

## In the admin

The demo exposes the audit trail through a `read_only` Activity log resource. See
[Actions](../admin/actions.md) and the `AdminDeps.audit` hook in
[Permissions](../admin/permissions.md).
