"""What an operator did in the panel, written where it is read beside everything else the system records."""

from sqlalchemy.ext.asyncio import AsyncSession

from enums.log_category import LogCategory
from enums.log_level import LogLevel
from helpers.database_session_helper import DatabaseSessionHelper
from helpers.tracing import current_request
from models.user import User
from services.system_log_service import system_log_service


async def written(db: AsyncSession, author: User, action: str, resource: str, *records: int) -> None:
    """The account, the action and what it reached, and never the body: a payload carries passwords and secrets."""
    await DatabaseSessionHelper.refresh_expired(db, author)

    marks = {"action": action, "resource": resource, "records": list(records), "request": current_request.get()}

    await system_log_service.record(db, author.tenant_id, author.id, LogLevel.INFO, LogCategory.ADMIN, f"{author.username or author.token} {action} {resource} {', '.join(str(record) for record in records)}", marks)
