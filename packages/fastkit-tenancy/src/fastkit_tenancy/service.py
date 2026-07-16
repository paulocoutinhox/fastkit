from fastkit_core.errors.codes import TENANT_CROSS_ACCESS, TENANT_REQUIRED
from fastkit_core.errors.exceptions import TenantError
from fastkit_tenancy.constants import GLOBAL_TENANT_ID, is_global
from fastkit_tenancy.models import Tenant, TenantStatus
from fastkit_tenancy.repository import TenantRepository


class TenantService:
    """Resolves tenants from a code and enforces cross-tenant access rules."""

    def __init__(self, session_factory):
        self._session_factory = session_factory

    async def get_by_code(self, code: str) -> Tenant | None:
        async with self._session_factory() as session:
            return await TenantRepository(session).find_one(code=code)

    async def require_active(self, code: str) -> Tenant:
        tenant = await self.get_by_code(code)

        if tenant is None:
            raise TenantError(TENANT_REQUIRED, message=f"tenant '{code}' was not found")

        if tenant.status != TenantStatus.active.value:
            raise TenantError(TENANT_REQUIRED, message=f"tenant '{code}' is not active")

        return tenant

    def assert_access(self, identity_tenant_id: int | None, effective_tenant_id: int | None) -> None:
        """A tenant-local identity can only act inside its own tenant, global identities anywhere."""

        if is_global(identity_tenant_id):
            return

        if identity_tenant_id != effective_tenant_id:
            raise TenantError(TENANT_CROSS_ACCESS, message="identity cannot act on another tenant")


def resolve_effective_tenant(identity_tenant_id: int | None, requested_tenant_id: int | None) -> int:
    """Global identities adopt the requested tenant, tenant-local identities keep their own."""

    if is_global(identity_tenant_id):
        return requested_tenant_id if requested_tenant_id is not None else GLOBAL_TENANT_ID

    return identity_tenant_id
