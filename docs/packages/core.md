# fastkit-core

The runtime foundation every other package builds on.

## What it provides

- **Apps + Runtime** — `FastKitApp`, `BootstrapContext`, app discovery and dependency-ordered
  bootstrap, `create_application(settings)`. See [Apps and lifecycle](../concepts/apps-lifecycle.md)
  and [Runtime and registries](../concepts/runtime-registries.md).
- **Registries** — models, routers, templates.
- **Service container** — components + resolved services, concurrency-safe. See
  [Service container](../concepts/service-container.md).
- **Request context** — per-request `request_id`/`user_id`/`tenant_id`/`locale`. See
  [Request context](../concepts/request-context.md).
- **API envelope** — `success_envelope`, `build_message`, pagination. See
  [Response envelope](../concepts/response-envelope.md).
- **Errors** — `ErrorCode`, exceptions, and the four exception handlers with i18n message resolution.
  See [Errors and i18n](../concepts/errors-and-i18n.md).
- **Events** — `EventBus`. See [Events](../concepts/events.md).
- **Health + system checks**. See [Health and system checks](../concepts/health-checks.md).
- **Resilience** — `CircuitBreaker`, `RetryPolicy`, `run_with_retry`. See
  [Resilience](../concepts/resilience.md).
- **Providers** — `ProviderRegistry`. See [Providers](../concepts/providers.md).
- **Sanitize** — `fastkit_core.sanitize.sanitize_html`, the one shared XSS-safe HTML sanitizer
  (allow-list tags/attrs/URL schemes, drops `on*`, `script`/`style`, `javascript:`/non-image
  `data:`).

## App

`CoreApp` (`fastkit.core`) — required by every other app.
