class BootstrapContext:
    """Passed to every app during bootstrap, exposing the shared runtime surfaces."""

    def __init__(self, runtime):
        self.runtime = runtime
        self.settings = runtime.settings
        self.services = runtime.services
        self.events = runtime.events
        self.health = runtime.health
        self.checks = runtime.checks
        self.models = runtime.models
        self.routers = runtime.routers
        self.templates = runtime.templates

    def registry(self, name: str):
        return self.runtime.registry(name)

    def component(self, name: str):
        return self.runtime.component(name)

    def set_component(self, name: str, value) -> None:
        self.runtime.set_component(name, value)


class FastKitApp:
    """Declarative unit registered in a FastKit runtime, similar to a Django AppConfig."""

    name: str = ""
    label: str = ""
    version: str = "0.0.0"
    requires: tuple[str, ...] = ()

    def register_settings(self, context: BootstrapContext) -> None:
        pass

    def register_models(self, context: BootstrapContext) -> None:
        pass

    def register_services(self, context: BootstrapContext) -> None:
        pass

    def register_templates(self, context: BootstrapContext) -> None:
        pass

    def register_translations(self, context: BootstrapContext) -> None:
        pass

    def register_tasks(self, context: BootstrapContext) -> None:
        pass

    def register_admin(self, context: BootstrapContext) -> None:
        pass

    def register_routers(self, context: BootstrapContext) -> None:
        pass

    def register_checks(self, context: BootstrapContext) -> None:
        pass

    async def startup(self, context: BootstrapContext) -> None:
        pass

    async def shutdown(self, context: BootstrapContext) -> None:
        pass
