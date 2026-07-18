# Add a cache provider

Register a factory in the module-level `cache_providers` registry, at import time, then select it in
settings.

```python
# app/providers.py — imported when your app module loads
from fastkit_cache.providers import cache_providers
from fastkit_cache.provider import CacheStatus

class MemcachedCacheProvider:
    def __init__(self, url):
        self._client = connect(url)

    async def get(self, key): ...
    async def set(self, key, value, ttl_seconds=None): ...
    async def delete(self, key): ...
    async def increment(self, key, amount=1): ...
    async def health(self):
        return report(CacheStatus.healthy)   # or degraded / unavailable

def build_memcached(settings, context):
    return MemcachedCacheProvider(settings.cache.memcached_url)

cache_providers.register("memcached", build_memcached)
```

Make sure `app/providers.py` is imported (import it from your `FastKitApp` module) so the registration
runs during app discovery.

Select it:

```toml
[cache]
provider = "memcached"
```

Implement `health()` returning a `CacheStatus` — the cache health check resolves the live provider, so
yours is what `/health` probes. See [Providers](../concepts/providers.md) and
[cache package](../packages/cache.md).
