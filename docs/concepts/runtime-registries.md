# Runtime and registries

## The Runtime

`Runtime` is the bootstrap engine. Given `settings` and the list of `installed_apps`, it:

1. discovers the app classes (`fastkit.apps` entry points),
2. instantiates the selected apps and orders them by `requires`,
3. runs each lifecycle phase across all apps in order,
4. builds the model / router / template registries, the service container, and health/system checks.

```python
from fastkit_core.runtime import Runtime, create_application

runtime = Runtime(settings=settings, installed_apps=list(settings.installed_apps))
runtime.bootstrap()

app = create_application(settings)     # builds the FastAPI app and sets app.state.fastkit = runtime
```

`create_application` also installs the **request-context middleware** and the **exception handlers**
and mounts the collected routers.

## Registries

Registries are how apps contribute without knowing about each other.

### Model registry

```python
context.models.register(Product, source=self.name)
```

`ModelRegistry.register` retains each model's `source` and names it in a duplicate-registration
error. `runtime.models.all()` returns every registered model — the DB layer uses it to create tables.

### Router registry

```python
context.routers.include(build_admin_router(site, deps), prefix=settings.admin.api_path, source=self.name)
```

Routers are collected and mounted by `create_application`.

### Template registry

Apps add template directories; the admin's `AdminRenderer` searches **consumer override directories
before** the package templates, so a project customizes a screen by dropping a same-named file in its
own `templates/` dir (Django-style). See [Templates & rendering](../admin/templates-rendering.md).

## Health and system checks

`HealthCheckRegistry` collects probes registered via `context.health.register(name, probe)`. Each
probe is isolated: `HealthCheckRegistry.run` catches a raising probe and reports it `unavailable`
with the error detail — a broken probe degrades the report, it never 500s `/health`. Cache and
storage providers register a health check that resolves the **live** component at check time
(`context.component("cache")`), so a consumer that overrides the provider gets a health check for its
provider.

See [Service container](service-container.md) and [Health and system checks](health-checks.md).
