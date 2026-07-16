import logging

from fastkit_core.errors.codes import AUTHORIZATION_DENIED
from fastkit_core.errors.exceptions import AuthorizationError

logger = logging.getLogger("fastkit.authorization")


class Authorizer:
    """Backend-authoritative authorization with an optional, fail-open-to-database cache."""

    def __init__(self, permission_service, cache=None):
        self._service = permission_service
        self._cache = cache

    async def permissions_for(self, user, tenant_id: int | None) -> set[str]:
        if self._cache is None:
            return await self._service.compute_permissions(user.id, tenant_id)

        cached = self._safe_cache_get(user.id, tenant_id)

        if cached is not None:
            return cached

        observed_version = self._cache.version
        computed = await self._service.compute_permissions(user.id, tenant_id)
        self._safe_cache_set(user.id, tenant_id, computed, observed_version)

        return computed

    async def has_permission(self, user, permission: str, tenant_id: int | None = None) -> bool:
        if not getattr(user, "is_active", True):
            return False

        if getattr(user, "is_root", False):
            return True

        return permission in await self.permissions_for(user, tenant_id)

    async def require(self, user, permission: str, tenant_id: int | None = None) -> None:
        if not await self.has_permission(user, permission, tenant_id):
            raise AuthorizationError(AUTHORIZATION_DENIED, message=f"permission '{permission}' is required")

    def _safe_cache_get(self, user_id, tenant_id):
        try:
            return self._cache.get(user_id, tenant_id)
        except Exception:
            logger.warning("permission cache read failed, falling back to database", exc_info=True)

            return None

    def _safe_cache_set(self, user_id, tenant_id, permissions, observed_version) -> None:
        try:
            self._cache.set(user_id, tenant_id, permissions, observed_version)
        except Exception:
            logger.warning("permission cache write failed, ignoring", exc_info=True)
