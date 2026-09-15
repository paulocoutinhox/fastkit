from helpers.crud import build_router
from schemas.tenant import TenantCreate, TenantSchema, TenantUpdate
from services.tenant import tenant_service

router = build_router(tenant_service, TenantSchema, TenantCreate, TenantUpdate, "/tenants", "tenants")
