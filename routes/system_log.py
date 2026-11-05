from helpers.crud import build_readonly_router
from schemas.system_log_schema import SystemLogSchema
from services.system_log_service import system_log_service

router = build_readonly_router(system_log_service, SystemLogSchema, "/system-logs", "system logs")
