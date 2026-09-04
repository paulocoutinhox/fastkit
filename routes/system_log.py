from helpers.crud import build_readonly_router
from schemas.system_log import SystemLogSchema
from services.system_log import system_log_service

router = build_readonly_router(system_log_service, SystemLogSchema, "/system-logs", "system logs")
