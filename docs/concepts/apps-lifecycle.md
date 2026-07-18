# Apps and lifecycle

An **app** is a `FastKitApp` subclass (`fastkit_core.apps.base`). It is the unit of composition: every
FastKit package ships one, and your project ships its own.

```python
from fastkit_core.apps.base import BootstrapContext, FastKitApp

class MyApp(FastKitApp):
    name = "myproject"
    label = "My project"
    version = "1.0.0"
    requires = ("fastkit.core", "fastkit.db", "fastkit.admin")
    # lifecycle hooks below
```

## Discovery and ordering

Apps are discovered through the **`fastkit.apps` entry point group**. Your package declares:

```toml
[project.entry-points."fastkit.apps"]
"myproject" = "app.my_app:MyApp"
```

The **Runtime** collects the installed apps listed in `settings.installed_apps`, then bootstraps them
in **dependency order** derived from each app's `requires`. `requires` is ordering only — it does not
install anything; it guarantees that, say, `fastkit.db` is bootstrapped before your app that needs a
`database` component.

## Lifecycle hooks

Every hook receives a `BootstrapContext` and is optional. They run in phases, across all apps in
dependency order:

| Hook | Purpose |
|---|---|
| `register_settings` | Contribute/adjust settings. |
| `register_models` | `context.models.register(Model, source=self.name)`. |
| `register_services` | Build and `context.set_component("name", instance)`; read others with `context.component("name")`. |
| `register_templates` | Add template directories. |
| `register_translations` | `context.component("translator").add_catalog(locale, {...})`. |
| `register_tasks` | Register task handlers on `context.component("task_registry")`. |
| `register_admin` | Register admin resources + menu on `context.component("admin_site")`. |
| `register_routers` | `context.routers.include(router, prefix=…, source=self.name)`. |
| `startup` / `shutdown` | Async lifecycle (spawn/cancel background work). |

Because hooks run in dependency order, a consumer app that `requires` a framework app can rely on the
framework app's components already being registered when its own `register_services` runs. This is
exactly how a consumer registers a custom login-identifier normalizer, a cache/storage/captcha
provider, or a task handler **without editing the framework**.

## The BootstrapContext

`context` exposes:

- `context.settings` — the typed settings.
- `context.models` / `context.routers` — registries.
- `context.component(name)` / `context.set_component(name, obj)` — the service container.
- `context.health` — register health/system checks.
- `context.templates` — the template registry.

## Example: contribute a service that reuses framework components

```python
def register_services(self, context):
    normalizers = context.component("normalizer_registry")   # from fastkit.accounts
    normalizers.register(MyIdentifierNormalizer())            # live immediately in login + create
```

See also [Runtime and registries](runtime-registries.md), [Service container](service-container.md),
and [Providers](providers.md).
