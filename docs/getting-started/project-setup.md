# Project setup

FastKit ships the generic wiring so a new project writes only its own apps, models, resources and
business rules — never the boilerplate every FastKit app shares. `examples/demo` is the reference;
this page walks the moving parts a project actually assembles.

## 1. `settings.py`

Load layered settings from TOML + environment:

```python
from fastkit_config import load_settings

CONFIG_DIR = "config"
settings = load_settings(CONFIG_DIR, environment="dev")
```

`load_settings` layers `base.toml` + `<env>.toml` + `FASTKIT__SECTION__FIELD` environment overrides.
See [Configuration](configuration.md).

## 2. `main.py`

Build the FastAPI app and mount the admin client + vendored assets:

```python
from fastkit_core.runtime import create_application
from fastkit_admin.mounting import mount_admin_static

from app.settings import settings

app = create_application(settings)   # sets app.state.fastkit = runtime
mount_admin_static(app)              # serves app.js/admin.css + every fastkit-vendor-* package
```

Mount your own media/static directories alongside `mount_admin_static`.

## 3. Your app

A `FastKitApp` subclass listing `requires` (ordering only) and lifecycle hooks:

```python
from fastkit_core.apps.base import BootstrapContext, FastKitApp

class MyApp(FastKitApp):
    name = "myproject"
    requires = ("fastkit.core", "fastkit.db", "fastkit.admin", "fastkit.auth",
                "fastkit.accounts", "fastkit.permissions")

    def register_models(self, context: BootstrapContext) -> None:
        context.models.register(Product, source=self.name)

    def register_admin(self, context: BootstrapContext) -> None:
        site = context.component("admin_site")
        instance = ProductAdmin()
        instance.assets = context.component("file_service")     # file lifecycle
        instance.media_base_url = context.settings.storage.base_url
        site.register(instance)
        site.add_group("catalog", "Catalog", order=0, icon="package")
        site.add_menu("Products", group="catalog", resource="products")

    def register_routers(self, context: BootstrapContext) -> None:
        ...
```

Every hook is optional. See [Apps and lifecycle](../concepts/apps-lifecycle.md).

## 4. Admin deps — do not hand-write them

```python
from fastkit_admin.security import build_admin_deps

deps, security = build_admin_deps(runtime, audit=audit)
```

`build_admin_deps` returns `(deps, security)` fully wired from the runtime components: cookie-session
auth (cookie name from `settings.auth.session_cookie_name`), `authorize`, locale resolution, and
`translate` (auto-wired from the runtime translator). The returned `AdminSecurity` backs every other
router that authenticates a request.

## 5. Generic routers ship from their owning packages

Mount them, do not copy them:

- `build_role_router(runtime, security)` — role/permission editor (fastkit-permissions).
- `build_content_router(runtime, security)` — per-language content (fastkit-content).
- `build_admin_router(site, deps)` — the CRUD `/api` for every resource.
- `build_profile_router(...)` — self-service profile (see [Login](../admin/login-and-captcha.md)).
- `build_upload_router(...)` — uploads keyed by kind.
- `build_admin_pages_router(...)` — the server-rendered screens.

Each generic router is duck-typed on `security`; permission strings and tenant are parameters with
sensible defaults, so authorization policy stays in your project.

## 6. First-class in-process worker

Set `tasks.run_worker` (or `FASTKIT__TASKS__RUN_WORKER=true`) and the running server also drains the
task queue. Register handlers with `registry.task(...)`. See
[Scheduled tasks and the worker](../guides/scheduled-tasks-worker.md).

## What stays in your project

Genuinely app-specific things: your models and admin resources, your menu, your authorization policy
(which permission guards what), and endpoints encoding business rules. Everything else is framework.
