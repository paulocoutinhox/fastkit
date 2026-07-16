from fastkit_core.apps.base import BootstrapContext, FastKitApp


class CoreApp(FastKitApp):
    """Root application every other FastKit app depends on."""

    name = "fastkit.core"
    label = "core"
    version = "1.0.0"

    def register_services(self, context: BootstrapContext) -> None:
        context.set_component("event_bus", context.events)
