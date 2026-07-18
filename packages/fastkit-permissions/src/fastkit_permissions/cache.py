class PermissionCache:
    """In-memory permission cache keyed by user, tenant and a global version counter."""

    def __init__(self):
        self._version = 1
        self._entries: dict[str, set[str]] = {}

    @property
    def version(self) -> int:
        return self._version

    def bump_version(self) -> None:
        self._version += 1
        self._entries.clear()

    def _key(self, user_id: str, tenant_id: int | None) -> str:
        return f"{user_id}:{tenant_id}:{self._version}"

    def get(self, user_id: str, tenant_id: int | None) -> set[str] | None:
        return self._entries.get(self._key(user_id, tenant_id))

    def set(
        self,
        user_id: str,
        tenant_id: int | None,
        permissions: set[str],
        observed_version: int,
    ) -> None:
        if observed_version != self._version:
            return

        self._entries[self._key(user_id, tenant_id)] = set(permissions)
