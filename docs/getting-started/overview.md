# Overview

FastKit is a modular, asynchronous ecosystem for FastAPI applications, shipped as a **monorepo of
independently versioned Python distributions**. You install only the packages you need, and your
project contributes apps, models, admin resources, providers and system checks through public
registries and contracts. **Business rules live in your project; FastKit provides generic,
predictable infrastructure.**

## Principles

- **Async everywhere.** Every IO path is `async`.
- **100% branch coverage** per package, and the admin is verified end-to-end in a real browser.
- **No hidden magic.** Apps are discovered through entry points, wired in dependency order, and
  everything is a registry, a provider, or a lifecycle hook you can see and override.
- **The framework gives possibilities, not fixed opinions.** Names, permissions, providers, locales,
  login layout and captcha are all configuration or extension points — never hardcoded rules.

## How the pieces fit

```
your project  ──►  a FastKitApp subclass (requires + lifecycle hooks)
                      │  register_models / register_services / register_admin / register_routers …
                      ▼
Runtime.bootstrap()  ──►  builds registries (models, routers, templates),
                          a service container, health + system checks, and the FastAPI app
```

A **Runtime** discovers installed apps (`fastkit.apps` entry points), bootstraps them in dependency
order, and exposes a component/service container. `create_application(settings)` builds the FastAPI
app, installs the request-context middleware and the exception handlers, and mounts routers.

## The packages

| Layer | Packages |
|---|---|
| Runtime & data | [core](../packages/core.md), [config](../packages/config.md), [db](../packages/db.md) |
| Identity | [accounts](../packages/accounts.md), [permissions](../packages/permissions.md), [auth](../packages/auth.md), [tenancy](../packages/tenancy.md) |
| Infrastructure | [cache](../packages/cache.md), [storage](../packages/storage.md), [files](../packages/files.md), [tasks](../packages/tasks.md), [mail](../packages/mail.md), [logging](../packages/logging.md) |
| Content & i18n | [i18n](../packages/i18n.md), [content](../packages/content.md) |
| Presentation | [admin](../packages/admin.md), [reports](../packages/reports.md), [vendor packages](../packages/vendors.md) |
| Integration & tooling | [webhooks](../packages/webhooks.md), [cli](../packages/cli.md), [testkit](../packages/testkit.md) |

Each package is a `src`-layout distribution with its own `DOCS.md`, `pyproject.toml` and `tests/`,
and declares a `fastkit.apps` entry point so the runtime can discover its `FastKitApp`.

## The response envelope

Every API response is a stable envelope:

```json
{ "success": true, "message": { "code": "…", "text": "…" } , "data": {}, "errors": [], "meta": {} }
```

Errors carry a stable `code` and a translated `text`. See
[Response envelope](../concepts/response-envelope.md).

## Next

- [Installation](installation.md) — get the environment running.
- [Project setup](project-setup.md) — wire a consumer project end to end.
- [Configuration](configuration.md) — settings from TOML + environment.
