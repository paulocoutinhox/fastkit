from sqlalchemy.ext.asyncio import AsyncSession

from enums.system_log import LogCategory, LogLevel
from models.system_log import SystemLog
from services.crud import CrudService


class SystemLogService(CrudService):
    model = SystemLog
    search_fields = ("category", "description")
    filter_fields = ("tenant_id", "user_id", "level", "category")
    ordering_fields = ("id", "level", "category", "created_at")
    default_ordering = "-id"
    relations = ("tenant", "user")
    label_fields = ("category",)

    async def record(self, db: AsyncSession, tenant_id: int | None, user_id: int | None, level: LogLevel, category: LogCategory | None, description: str, meta: dict | None = None) -> SystemLog:
        entry = SystemLog(tenant_id=tenant_id, user_id=user_id, level=level, category=category, description=description, meta=meta or {})

        db.add(entry)
        await self.persist(db)

        return entry


system_log_service = SystemLogService()
