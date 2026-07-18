# fastkit-cache

Cache for FastKit with a single contract and file and database providers (both
DB/disk-backed, no external server dependency). Only the configured provider is used —
there is no automatic fallback.

## Installation

```bash
pip install fastkit-cache
```

## Providers

- `FileCacheProvider` — single node, atomic writes, TTL, namespace clearing.
- `DatabaseCacheProvider` — portable `cache_entry` table, unique per
  `(namespace, key_hash)`.

Providers are pluggable by name: `cache_providers.register("redis", factory)`
(`fastkit_cache.providers`) adds an external backend (Redis, Memcached, …) a project
brings and selects via `settings.cache.provider`.

## Namespacing

Keys are `fastkit:{environment}:{tenant}:{version}:{namespace}:{key}`. Preferred
invalidation bumps the namespace version so old keys expire rather than being
scanned.

## Facade

```python
await cache.set("users", user_id, payload, tenant_id=5, ttl=60)
value = await cache.get("users", user_id, tenant_id=5)
await cache.clear_namespace("users")
```

## Testing

100% branch coverage, including circuit open/recover, degradation and TTL expiry.

```bash
pytest packages/fastkit-cache --cov=fastkit_cache --cov-branch
```
