# Providers

A **provider** is a swappable backend for a subsystem, selected by name through settings. FastKit
ships the built-ins and lets you register your own **without editing the framework**. This is the
single pattern behind cache, storage, mail and captcha.

## The registry

`fastkit_core.providers.ProviderRegistry` is a named-factory registry:

```python
class ProviderRegistry:
    def __init__(self, kind): ...
    def register(self, name, factory): ...
    def build(self, name, *args):
        # returns factory(*args); raises ValueError for an unknown name
```

Each subsystem exposes a **module-level** registry with the built-ins registered at import time:

- `fastkit_cache.providers.cache_providers` — `file`, `database`
- `fastkit_storage.providers.storage_providers` — `local`, `s3`
- `fastkit_mail.providers.mail_providers`
- `fastkit_auth.captcha.providers.captcha_providers` — `disabled`, `recaptcha`, `image`

The app builds the selected provider from `settings.<subsystem>.provider`:

```python
provider = cache_providers.build(settings.cache.provider, settings, context)
```

## Registering your own provider

Import the module-level registry and register a factory at **import time** (so it runs during app
discovery, before any `register_services` builds the provider):

```python
# app/providers.py — imported by your FastKitApp module
from fastkit_cache.providers import cache_providers

def build_memcached(settings, context):
    return MemcachedCacheProvider(settings.cache.memcached_url)

cache_providers.register("memcached", build_memcached)
```

Then select it in settings:

```toml
[cache]
provider = "memcached"
```

The consumer's `settings.cache.memcached_url` is a field it adds to its own settings extension (or
reads from the environment inside the factory).

## Why module-level, at import time

App discovery imports every installed app's module before the runtime runs `register_services`. A
top-level `registry.register(...)` in your app's module therefore runs first, so the framework app's
`register_services` (which calls `registry.build(settings.provider)`) already sees your factory. No
ordering problem.

## Other extension registries

The same shape appears for tasks, webhooks and reports (their own registries), for vendored
front-end libraries (`fastkit.assets` entry point), and for translations
(`translator.add_catalog`). See the specific package docs.

Guides: [Add a cache provider](../guides/add-cache-provider.md),
[Add a mail provider](../guides/add-mail-provider.md),
[Add a captcha provider](../guides/add-captcha-provider.md),
[Configure storage (local/S3/R2)](../guides/configure-storage-local-s3-r2.md).
