from datetime import timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from helpers.dates import now
from helpers.settings import settings
from helpers.storage import storage
from models.upload import StoredFile

# The pass walks its own rows and never the bucket, so what it holds at once is this and never the size of the storage.
BATCH = 1000


class SweepService:
    """A file nothing claimed within the grace window, read from the rows this application wrote rather than from a listing of the bucket."""

    def waiting(self):
        return select(StoredFile).where(StoredFile.claimed_at.is_(None), StoredFile.created_at < now() - timedelta(hours=settings.storage.orphan_grace_hours)).order_by(StoredFile.id.asc()).limit(BATCH)

    async def find_orphans(self, db: AsyncSession) -> list[str]:
        """A file written moments ago has no row yet, so only what survived the grace window is considered."""
        return [record.key for record in (await db.execute(self.waiting())).scalars()]

    async def discard_orphans(self, db: AsyncSession) -> list[str]:
        discarded = []

        while True:
            waiting = list((await db.execute(self.waiting())).scalars())

            if not waiting:
                return discarded

            for record in waiting:
                await storage.delete(record.key)
                discarded.append(record.key)

            # The row goes after the file, or a pass cut in half would leave a file nothing names again.
            await db.execute(delete(StoredFile).where(StoredFile.id.in_([record.id for record in waiting])))
            await db.commit()


sweep_service = SweepService()
