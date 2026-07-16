from fastkit_core.apps.base import BootstrapContext, FastKitApp
from fastkit_core.apps.loader import discover_apps, instantiate_selected, order_apps
from fastkit_core.checks.base import SystemCheckRegistry
from fastkit_core.events.bus import EventBus
from fastkit_core.health.base import HealthCheckRegistry
from fastkit_core.registries.base import Registry
from fastkit_core.registries.components import ModelRegistry, RouterRegistry, TemplateRegistry
from fastkit_core.services.container import ServiceContainer


class Runtime:
    """Holds every shared surface and drives the deterministic bootstrap sequence."""

    def __init__(self, settings, installed_apps: list[str]):
        self.settings = settings
        self.installed_apps = installed_apps

        self.services = ServiceContainer()
        self.events = EventBus()
        self.health = HealthCheckRegistry()
        self.checks = SystemCheckRegistry()
        self.models = ModelRegistry()
        self.routers = RouterRegistry()
        self.templates = TemplateRegistry()

        self._registries: dict[str, Registry] = {}
        self._components: dict[str, object] = {}
        self._apps: list[FastKitApp] = []
        self._context = BootstrapContext(self)
        self.ready = False

    def registry(self, name: str) -> Registry:
        if name not in self._registries:
            self._registries[name] = Registry(name)

        return self._registries[name]

    def component(self, name: str):
        if name not in self._components:
            raise KeyError(f"component '{name}' is not registered")

        return self._components[name]

    def try_component(self, name: str):
        return self._components.get(name)

    def set_component(self, name: str, value) -> None:
        self._components[name] = value

    @property
    def apps(self) -> list[FastKitApp]:
        return list(self._apps)

    def bootstrap(self) -> None:
        available = discover_apps()
        selected = instantiate_selected(self.installed_apps, available)
        self._apps = order_apps(selected)

        for app in self._apps:
            app.register_settings(self._context)

        for app in self._apps:
            app.register_models(self._context)

        for app in self._apps:
            app.register_services(self._context)

        for app in self._apps:
            app.register_templates(self._context)

        for app in self._apps:
            app.register_translations(self._context)

        for app in self._apps:
            app.register_tasks(self._context)

        for app in self._apps:
            app.register_admin(self._context)

        for app in self._apps:
            app.register_routers(self._context)

        for app in self._apps:
            app.register_checks(self._context)

        self.checks.run_or_raise()

    async def start(self) -> None:
        for app in self._apps:
            await app.startup(self._context)

        self.ready = True

    async def stop(self) -> None:
        self.ready = False

        for app in reversed(self._apps):
            await app.shutdown(self._context)

        await self.services.shutdown()
