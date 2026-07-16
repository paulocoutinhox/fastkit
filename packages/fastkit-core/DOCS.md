# fastkit-core

Core runtime for the FastKit ecosystem. It owns the app system, registries, the
service container, the request context, the unified API envelope and the error
taxonomy. It has no dependency on SQLAlchemy, Redis, boto3, Pillow or Tabler.

## Installation

```bash
pip install fastkit-core
```

## Concepts

### Apps

Every module ships a `FastKitApp` describing what it contributes and what it
requires. Apps are discovered through the `fastkit.apps` entry point group and
activated explicitly through `INSTALLED_APPS`.

```python
from fastkit_core.apps.base import FastKitApp


class MailApp(FastKitApp):
    name = "fastkit.mail"
    requires = ("fastkit.core", "fastkit.db")

    def register_services(self, context):
        ...
```

### Runtime and bootstrap

`Runtime` drives a deterministic bootstrap: discover apps, resolve the dependency
graph, then run each registration phase in order (settings, models, services,
templates, translations, tasks, admin, routers, checks) before running the system
checks. Importing a package never triggers these effects.

### FastKit facade

```python
from fastkit_core.app import FastKit, create_application

app = create_application(settings)
```

`FastKit.install` mounts the request-context middleware, the envelope exception
handlers and every registered router. `app.state.fastkit` exposes the runtime.

### Service container

Supports `singleton`, `scoped` and `transient` lifetimes, async factories,
circular-dependency detection, overrides for tests and ordered async shutdown.

### Registries

Generic `Registry` with duplicate detection, source tracking, priority ordering
and `freeze()`. Concrete `ModelRegistry`, `RouterRegistry` and `TemplateRegistry`
back the runtime.

### API envelope

Every FastKit-managed response uses a single envelope with `success`, `message`,
`data`, `errors` and `meta`. `RequestValidationError` is normalized into stable
`validation.*` codes so the raw Pydantic format is never exposed.

### Errors

`ErrorCode` carries a stable code, HTTP status, translation key, severity, retry
hint and logging policy. `FastKitError` and its subclasses map onto the envelope
through the installed handlers.

### Events, health and system checks

An ordered async `EventBus` isolates non-critical handlers behind timeouts.
`HealthCheckRegistry` aggregates the worst reported status and
`SystemCheckRegistry` aborts the bootstrap on any error.

### Resilience

`fastkit_core.resilience` provides the shared building blocks used across packages
to survive dependency failures and connection drops:

- `CircuitBreaker` opens after a failure threshold and half-opens after a cooldown
  to probe recovery, so a persistently unhealthy dependency fails fast and
  reconnects on its own.
- `RetryPolicy` describes bounded exponential backoff with jitter.
- `run_with_retry(operation, policy, breaker=...)` runs an async operation with
  retries and an optional breaker, logging every failure.

```python
breaker = CircuitBreaker(failure_threshold=5)
await run_with_retry(lambda: client.call(), RetryPolicy(max_attempts=3), breaker=breaker, name="provider.call")
```

The cache Redis provider, the mail service and the S3 storage provider are built on
these. The database engine uses `pool_pre_ping` and `pool_recycle`. Errors surfaced
to clients carry a translated `message.text` resolved from the runtime translator.

## Testing

100% branch coverage.

```bash
pytest packages/fastkit-core --cov=fastkit_core --cov-branch
```
