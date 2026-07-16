# fastkit-logging

Structured logging for FastKit: a rotating `logs/app.log`, JSON lines in stage
and prod, request correlation, an immutable `AuditLog` and an event-oriented
`SystemLog`, with automatic sanitization of sensitive fields.

## Installation

```bash
pip install fastkit-logging
```

## Configuration

`setup_logging` installs a rotating file handler and a console handler on the
root logger. In `stage` and `prod` both use JSON lines enriched with the current
request id, tenant id and user id.

```python
from fastkit_logging.config import setup_logging

setup_logging(level="INFO", file_path="logs/app.log", environment="prod")
```

## Request logging

`RequestLoggingMiddleware` logs one structured line per request with method,
path, status and duration, and logs failures with a stack trace before
re-raising.

## SystemLog and AuditLog

`SystemLogService.record` always writes to `app.log` first, then best-effort
persists a `SystemLog` row — a database failure never suppresses the file entry.
`AuditLogService.record` stores a `create/update/delete/...` action with
sanitized before/after snapshots.

```python
await system_log_service.record("ERROR", "database", "down", "connection lost")
await audit_log_service.record("update", "User", resource_id="1", before=old, after=new)
```

## Sanitization

`sanitize` recursively redacts keys such as `password`, `token`, `authorization`,
`secret`, `cookie` and `private_key` before anything is logged or persisted.

## Testing

100% branch coverage.

```bash
pytest packages/fastkit-logging --cov=fastkit_logging --cov-branch
```
