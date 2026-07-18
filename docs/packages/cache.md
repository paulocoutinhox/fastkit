# fastkit-cache

A cache contract with file and database providers, selected by settings.

## Use

```python
cache = context.component("cache")
await cache.set("key", value, ttl_seconds=60)
value = await cache.get("key")
```

## Providers

Selected by `settings.cache.provider`:

- **`file`** — on-disk (default).
- **`database`** — a `CacheEntry` table.

Both ship with the framework. A consumer that wants an external cache (Redis, Memcached, …) registers
its own provider with `cache_providers.register("name", factory)` — see
[Add a cache provider](../guides/add-cache-provider.md) and [Providers](../concepts/providers.md).

## Health

The cache provider registers a health check that resolves the **live** component at check time, so an
overridden provider is the one probed.

## Known follow-ups

The database/file cache `increment` does not preserve TTL, and `set` is check-then-write
(fine on SQLite's single writer; wants an upsert on Postgres). Documented, to be fixed with real
atomicity.
