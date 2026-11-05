from helpers.crud import build_router
from schemas.tenant_create import TenantCreate
from schemas.tenant_schema import TenantSchema
from schemas.tenant_update import TenantUpdate
from services.tenant_service import tenant_service

router = build_router(tenant_service, TenantSchema, TenantCreate, TenantUpdate, "/tenants", "tenants")
