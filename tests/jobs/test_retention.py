from datetime import timedelta

from sqlalchemy import func, select, update

from enums.system_log import LogCategory, LogLevel
from helpers.dates import now
from helpers.settings import settings
from jobs.retention import discard_expired_records
from models.system_log import SystemLog
from services.system_log import system_log_service


async def test_the_job_drops_what_the_window_no_longer_keeps(db, tenant):
    entry = await system_log_service.record(db, tenant.id, None, LogLevel.INFO, LogCategory.CRON, "an old pass", {})
    await db.commit()

    await db.execute(update(SystemLog).where(SystemLog.id == entry.id).values(created_at=now() - timedelta(days=settings.retention.system_log_days + 1)))
    await db.commit()

    await discard_expired_records()

    assert await db.scalar(select(func.count()).select_from(SystemLog).where(SystemLog.id == entry.id)) == 0
