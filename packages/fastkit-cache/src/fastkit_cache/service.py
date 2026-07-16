import json

from fastkit_cache.namespaces import build_key


class Cache:
    """High-level cache facade adding namespacing and JSON serialization over a provider."""

    def __init__(self, provider, environment: str, default_ttl: int, version: int = 1):
        self._provider = provider
        self._environment = environment
        self._default_ttl = default_ttl
        self._version = version

    def _key(self, namespace: str, key: str, tenant_id: int | None) -> str:
        return build_key(self._environment, tenant_id, self._version, namespace, key)

    async def get(self, namespace: str, key: str, tenant_id: int | None = None):
        raw = await self._provider.get(self._key(namespace, key, tenant_id))

        return None if raw is None else json.loads(raw)

    async def set(self, namespace: str, key: str, value, tenant_id: int | None = None, ttl: int | None = None) -> None:
        payload = json.dumps(value, separators=(",", ":")).encode("utf-8")

        await self._provider.set(self._key(namespace, key, tenant_id), payload, ttl if ttl is not None else self._default_ttl)

    async def delete(self, namespace: str, key: str, tenant_id: int | None = None) -> None:
        await self._provider.delete(self._key(namespace, key, tenant_id))

    async def clear_namespace(self, namespace: str) -> None:
        await self._provider.clear_namespace(namespace)

    async def health(self):
        return await self._provider.health()
