from fastkit_core.context.request import get_request_context
from fastkit_logging.models import AuditLog
from fastkit_logging.sanitize import sanitize


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
