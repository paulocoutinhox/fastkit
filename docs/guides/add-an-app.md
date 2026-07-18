# Add an app

Every project — and every reusable feature — is a `FastKitApp`.

## 1. Write the class

```python
# app/my_app.py
from fastkit_core.apps.base import BootstrapContext, FastKitApp

class MyApp(FastKitApp):
    name = "myproject"
    label = "My project"
    version = "1.0.0"
    requires = ("fastkit.core", "fastkit.db", "fastkit.admin", "fastkit.auth")

    def register_models(self, context: BootstrapContext) -> None:
        context.models.register(Product, source=self.name)

    def register_admin(self, context: BootstrapContext) -> None:
        site = context.component("admin_site")
        site.register(ProductAdmin())
        site.add_group("catalog", "Catalog", order=0, icon="package")
        site.add_menu("Products", group="catalog", resource="products")

    def register_routers(self, context: BootstrapContext) -> None:
        ...
```

## 2. Declare the entry point

```toml
# pyproject.toml
[project.entry-points."fastkit.apps"]
"myproject" = "app.my_app:MyApp"
```

## 3. Install it

```toml
# config/base.toml
installed_apps = ["fastkit.core", "fastkit.db", "fastkit.admin", "fastkit.auth", "myproject"]
```

The runtime discovers it, orders it after its `requires`, and runs its hooks. See
[Apps and lifecycle](../concepts/apps-lifecycle.md).
