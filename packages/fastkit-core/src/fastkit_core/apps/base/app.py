from fastkit_core.apps.base.bootstrap_context import BootstrapContext


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
