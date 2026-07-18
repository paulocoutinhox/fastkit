# Request context

The request-context middleware (installed by `create_application`) makes per-request data available
anywhere in the async call stack, without threading it through every function.

```python
from fastkit_core.context.request import get_request_context, update_request_context

ctx = get_request_context()   # request_id, user_id, tenant_id, locale …
update_request_context(user_id="42", tenant_id=7)
```

## What it carries

- **`request_id`** — stamped by the middleware onto `request.state.request_id`. A 500 envelope reads
  it from there (the context is already reset by the time `ServerErrorMiddleware` runs), so
  `meta.request_id` is the real request id, not a fresh random.
- **`user_id` / `tenant_id`** — the acting user is stamped when the current user resolves:
  `AdminSecurity.get_current_user` calls `update_request_context(user_id=…, tenant_id=user.tenant_id)`.
  `SystemLog`/`AuditLog` read `context.tenant_id`, so they record the **actor's** tenant, not `None`.
- **`locale`** — the resolved request locale.

## Why it matters

Audit and system logs, tenant scoping, and the request id in every envelope all rely on the context
being correct and isolated per request. It is a `ContextVar`, so concurrent requests never see each
other's data, and it is reset when the request completes.
