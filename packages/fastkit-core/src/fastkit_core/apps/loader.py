from importlib.metadata import entry_points

from fastkit_core.apps.base import FastKitApp


class AppLoadError(RuntimeError):
    pass


def discover_apps(group: str = "fastkit.apps") -> dict[str, type[FastKitApp]]:
    """Return every FastKitApp advertised through entry points, keyed by app name."""

    discovered: dict[str, type[FastKitApp]] = {}

    for entry in entry_points(group=group):
        app_class = entry.load()
        discovered[app_class.name] = app_class

    return discovered


def instantiate_selected(installed: list[str], available: dict[str, type[FastKitApp]]) -> list[FastKitApp]:
    seen: set[str] = set()
    apps: list[FastKitApp] = []

    for name in installed:
        if name in seen:
            raise AppLoadError(f"duplicate app '{name}' in INSTALLED_APPS")

        app_class = available.get(name)

        if app_class is None:
            raise AppLoadError(f"app '{name}' is not installed or not discoverable")

        seen.add(name)
        apps.append(app_class())

    return apps


def order_apps(apps: list[FastKitApp]) -> list[FastKitApp]:
    """Return apps ordered so every required dependency comes before its dependents."""

    by_name = {app.name: app for app in apps}

    for app in apps:
        for requirement in app.requires:
            if requirement not in by_name:
                raise AppLoadError(f"app '{app.name}' requires '{requirement}' which is not installed")

    ordered: list[FastKitApp] = []
    visited: set[str] = set()
    visiting: set[str] = set()

    def visit(app: FastKitApp) -> None:
        if app.name in visited:
            return

        if app.name in visiting:
            raise AppLoadError(f"circular dependency detected at '{app.name}'")

        visiting.add(app.name)

        for requirement in app.requires:
            visit(by_name[requirement])

        visiting.discard(app.name)
        visited.add(app.name)
        ordered.append(app)

    for app in apps:
        visit(app)

    return ordered
