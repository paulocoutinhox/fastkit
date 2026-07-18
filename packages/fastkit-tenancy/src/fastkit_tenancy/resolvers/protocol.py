from typing import Protocol, runtime_checkable


@runtime_checkable
class TenantResolver(Protocol):
    name: str

    def resolve(self, request) -> str | None:
        """Return a tenant code from the request, or None when this resolver does not apply."""
        ...
