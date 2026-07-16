from contextvars import ContextVar
from dataclasses import dataclass

from fastkit_tenancy.constants import GLOBAL_TENANT_ID, is_global


@dataclass(frozen=True)
class TenantContext:
    requested_tenant_id: int | None
    effective_tenant_id: int | None
    source: str
    resolved_at: str

    @property
    def is_global_scope(self) -> bool:
        return is_global(self.effective_tenant_id)


_current_tenant: ContextVar[TenantContext | None] = ContextVar("fastkit_tenant_context", default=None)


def get_tenant_context() -> TenantContext | None:
    return _current_tenant.get()


def require_tenant_context() -> TenantContext:
    context = _current_tenant.get()

    if context is None:
        raise LookupError("no tenant context is active for a tenant-scoped operation")

    return context


def set_tenant_context(context: TenantContext):
    return _current_tenant.set(context)


def reset_tenant_context(token) -> None:
    _current_tenant.reset(token)


def global_context(source: str = "system", resolved_at: str = "") -> TenantContext:
    return TenantContext(requested_tenant_id=GLOBAL_TENANT_ID, effective_tenant_id=GLOBAL_TENANT_ID, source=source, resolved_at=resolved_at)
