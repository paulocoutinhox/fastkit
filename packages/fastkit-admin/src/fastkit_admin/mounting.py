from pathlib import Path

from fastapi.staticfiles import StaticFiles

from fastkit_admin.assets import AssetRegistry

STATIC_DIR = Path(__file__).parent / "static"


def mount_assets(app, registry: AssetRegistry | None = None) -> None:
    """Serve every vendored front-end asset package from its own url prefix."""

    registry = registry or AssetRegistry.discover()

    for mount, directory in registry.mounts():
        app.mount(mount, StaticFiles(directory=directory), name=f"vendor-{mount.rsplit('/', 1)[-1]}")


def mount_admin_static(app, static_base: str = "/admin-static", registry: AssetRegistry | None = None) -> None:
    """Serve the admin client (app.js/admin.css) and every vendored asset package.

    A consumer calls this once after building the application, so the admin frontend needs
    no per-project static wiring.
    """

    app.mount(static_base, StaticFiles(directory=STATIC_DIR), name="admin-static")
    mount_assets(app, registry)
