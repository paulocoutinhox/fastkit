from fastkit_core.apps.base import BootstrapContext, FastKitApp
from fastkit_core.health.base import HealthResult, HealthStatus
from fastkit_storage.provider import StorageStatus
from fastkit_storage.providers import storage_providers

_STATUS_MAP = {StorageStatus.healthy: HealthStatus.healthy, StorageStatus.unavailable: HealthStatus.unavailable}


def build_provider(settings):
    return storage_providers.build(settings.storage.provider, settings)


class StorageApp(FastKitApp):
    name = "fastkit.storage"
    label = "storage"
    version = "1.0.0"
    requires = ("fastkit.core",)

    def register_services(self, context: BootstrapContext) -> None:
        context.set_component("storage", build_provider(context.settings))
        context.health.register("storage", lambda: self._health(context))

    async def _health(self, context: BootstrapContext) -> HealthResult:
        report = await context.component("storage").health()

        return HealthResult("storage", _STATUS_MAP[report.status], detail=report.detail)
