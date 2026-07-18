# Service container

The service container (`fastkit_core.services`) holds the shared components an app builds and the
services resolved on demand. It is where dependency injection happens.

## Components

A **component** is a singleton object registered by name during `register_services`:

```python
def register_services(self, context):
    context.set_component("asset_service", AssetService(...))

# elsewhere, in an app that requires this one:
service = context.component("asset_service")
```

Components are the primary integration surface: `database`, `cache`, `storage`, `file_service`,
`auth_service`, `admin_site`, `translator`, `task_registry`, `normalizer_registry`,
`captcha_provider`, and many more.

## Concurrency correctness

The container is safe under concurrent cold-start:

- **Singletons** are guarded by a per-key `asyncio.Lock` (double-checked), so a service is built
  exactly once even if two coroutines resolve it simultaneously.
- **Circular-dependency detection** uses a per-resolution-chain `ContextVar` (never a container-global
  set), so two independent concurrent resolutions can't raise a bogus "circular dependency".
- **Scoped services** (`ServiceScope`) use the same double-checked per-key lock, so two concurrent
  resolutions of one scoped key in a shared scope yield a single instance.

A genuinely circular **singleton** graph (A needs B needs A) raises `ServiceError` when resolved
sequentially — an impossible graph either way.

## Overriding a framework component

Because `register_services` runs in dependency order, a consumer app can replace a framework
component after the framework registered it:

```python
def register_services(self, context):
    context.set_component("cache_provider", MyCacheProvider(...))
```

Health checks and services that resolve `context.component(...)` at call time will pick up the
override. For providers selected by settings, prefer the provider registry pattern instead — see
[Providers](providers.md).
