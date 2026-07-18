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
