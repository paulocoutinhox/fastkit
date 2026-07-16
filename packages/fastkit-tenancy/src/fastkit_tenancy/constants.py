GLOBAL_TENANT_ID = 0


def to_persisted(api_tenant_id: int | None) -> int | None:
    """Map the public global tenant id (0) to the NULL persistence representation."""

    if api_tenant_id is None or api_tenant_id == GLOBAL_TENANT_ID:
        return None

    return api_tenant_id


def to_api(persisted_tenant_id: int | None) -> int:
    """Map the NULL persistence representation back to the public global tenant id (0)."""

    if persisted_tenant_id is None:
        return GLOBAL_TENANT_ID

    return persisted_tenant_id


def is_global(api_tenant_id: int | None) -> bool:
    return api_tenant_id is None or api_tenant_id == GLOBAL_TENANT_ID
