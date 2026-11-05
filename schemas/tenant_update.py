from schemas.common import as_optional
from schemas.tenant_create import TenantCreate

TenantUpdate = as_optional("TenantUpdate", TenantCreate)
