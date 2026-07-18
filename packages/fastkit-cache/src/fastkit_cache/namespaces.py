import hashlib


def build_key(
    environment: str,
    tenant_id: int | None,
    namespace_version: int,
    namespace: str,
    key: str,
) -> str:
    """Build a fully qualified cache key scoped by environment, tenant and namespace version."""

    tenant = "global" if tenant_id is None else str(tenant_id)

    return f"fastkit:{environment}:{tenant}:{namespace_version}:{namespace}:{key}"


def hash_key(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()
