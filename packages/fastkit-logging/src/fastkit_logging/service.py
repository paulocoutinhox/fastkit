import logging

from fastkit_core.context.request import get_request_context
from fastkit_logging.models import AuditLog, SystemLog
from fastkit_logging.sanitize import sanitize

logger = logging.getLogger("fastkit.system")


class SystemLogService:
    """Writes to app.log immediately, then best-effort persists a SystemLog row."""

    def __init__(self, database, environment: str):
        self._database = database
        self._environment = environment

    async def record(
        self,
        level: str,
        category: str,
        event: str,
        message: str,
        payload: dict | None = None,
        **fields,
    ) -> SystemLog | None:
        context = get_request_context()

        resolved_level = logging.getLevelName(level.upper())
        numeric_level = (
            resolved_level if isinstance(resolved_level, int) else logging.INFO
        )

        logger.log(numeric_level, "%s.%s %s", category, event, message)

        row = SystemLog(
            environment=self._environment,
            level=level,
            category=category,
            event=event,
            message=message,
            request_id=context.request_id,
            tenant_id=context.tenant_id,
            payload=sanitize(payload) if payload is not None else None,
            **fields,
        )

        return await self._persist(row)

    async def _persist(self, row):
        try:
            async with self._database.session_factory() as session:
                session.add(row)
                await session.commit()

            return row
        except Exception:
            logger.exception("failed to persist system log, app.log entry kept")

            return None


class AuditLogService:
    """Persists an immutable audit trail with sanitized before/after snapshots."""

    def __init__(self, database):
        self._database = database

    async def record(
        self,
        action: str,
        resource_type: str,
        resource_id: str | None = None,
        before: dict | None = None,
        after: dict | None = None,
    ) -> AuditLog:
        context = get_request_context()

        row = AuditLog(
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            tenant_id=context.tenant_id,
            effective_tenant_id=context.tenant_id,
            user_id=context.user_id,
            request_id=context.request_id,
            before_data=sanitize(before) if before is not None else None,
            after_data=sanitize(after) if after is not None else None,
        )

        async with self._database.session_factory() as session:
            session.add(row)
            await session.commit()
            await session.refresh(row)

        return row
