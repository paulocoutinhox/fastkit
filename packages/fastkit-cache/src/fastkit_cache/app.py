from fastkit_core.apps.base import BootstrapContext, FastKitApp
from fastkit_core.health.base import HealthResult, HealthStatus
from fastkit_cache.database import CacheEntry
from fastkit_cache.provider import CacheStatus
from fastkit_cache.providers import cache_providers
from fastkit_cache.service import Cache

_STATUS_MAP = {
    CacheStatus.healthy: HealthStatus.healthy,
    CacheStatus.degraded: HealthStatus.degraded,
    CacheStatus.unavailable: HealthStatus.unavailable,
}


def build_provider(settings, context: BootstrapContext):
    return cache_providers.build(settings.cache.provider, settings, context)


class CacheApp(FastKitApp):
    name = "fastkit.cache"
    label = "cache"
    version = "1.0.0"
    requires = ("fastkit.core", "fastkit.db")

    def register_models(self, context: BootstrapContext) -> None:
        context.models.register(CacheEntry, source=self.name)

    def register_services(self, context: BootstrapContext) -> None:
        settings = context.settings
        provider = build_provider(settings, context)
        cache = Cache(provider, settings.app.environment, settings.cache.default_ttl_seconds)

        context.set_component("cache_provider", provider)
        context.set_component("cache", cache)

        context.health.register("cache", lambda: self._health(context))

    async def _health(self, context: BootstrapContext) -> HealthResult:
        report = await context.component("cache_provider").health()

        return HealthResult("cache", _STATUS_MAP[report.status], detail=report.detail)
