import json

_DEFAULT_TTL_SECONDS = 300
_VERSION_KEY = "permissions:version"


class PermissionCache:
    """Permission cache over a `KeyValueStore`, keyed by user, tenant and a shared version counter.

    The version counter lives in the store, so a mutation on any worker invalidates every worker at
    once (the counter increment is atomic). The per-entry TTL is a safety net for a role or
    assignment mutated out of band (generic admin CRUD on the `Role` model), so stale authorization
    self-heals within `ttl_seconds` instead of persisting indefinitely.
    """

    def __init__(self, store, ttl_seconds: int | None = _DEFAULT_TTL_SECONDS):
        self._store = store
        self._ttl_seconds = ttl_seconds

    async def version(self) -> int:
        raw = await self._store.get(_VERSION_KEY)

        return int(raw.decode("utf-8")) if raw is not None else 0

    async def bump_version(self) -> None:
        await self._store.increment(_VERSION_KEY)

    def _key(self, user_id, tenant_id, version: int) -> str:
        return f"permissions:{user_id}:{tenant_id}:{version}"

    async def get(self, user_id, tenant_id) -> set[str] | None:
        version = await self.version()
        raw = await self._store.get(self._key(user_id, tenant_id, version))

        return set(json.loads(raw.decode("utf-8"))) if raw is not None else None

    async def set(self, user_id, tenant_id, permissions, observed_version: int) -> None:
        if await self.version() != observed_version:
            return

        payload = json.dumps(sorted(permissions)).encode("utf-8")
        await self._store.set(
            self._key(user_id, tenant_id, observed_version),
            payload,
            ttl=self._ttl_seconds,
        )
