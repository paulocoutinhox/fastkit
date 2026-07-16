# fastkit-cache

Cache for FastKit with a single contract and file, database and Redis providers.
Only the configured provider is used — there is no automatic fallback.

## Installation

```bash
pip install fastkit-cache
pip install "fastkit-cache[redis]"
```

## Providers

- `FileCacheProvider` — single node, atomic writes, TTL, namespace clearing.
- `DatabaseCacheProvider` — portable `cache_entries` table, unique per
  `(namespace, key_hash)`.
- `RedisCacheProvider` — pooled client wrapped in a `CircuitBreaker`. On failure
  it logs, degrades, opens the circuit and serves a miss, then half-opens after a
  cooldown to probe recovery. Cache failure never crashes the request.

Providers are pluggable by name: `cache_providers.register("memcached", factory)`
(`fastkit_cache.providers`) adds a backend a project selects via
`settings.cache.provider`.

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
