from collections.abc import AsyncIterator
from datetime import timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from helpers.dates import now
from helpers.settings import settings
from models.upload import StoredFile
from services.upload import upload_service

# The pass walks its own rows and never the bucket, so what it holds at once is this and never the size of the storage.
BATCH = 1000


class SweepService:
    """A file nothing claimed within the grace window, read from the rows this application wrote rather than from a listing of the bucket."""

    def waiting(self, after: int = 0):
        return select(StoredFile).where(StoredFile.claimed_at.is_(None), StoredFile.created_at < now() - timedelta(hours=settings.storage.orphan_grace_hours), StoredFile.id > after).order_by(StoredFile.id.asc()).limit(BATCH)

    async def find_orphans(self, db: AsyncSession) -> AsyncIterator[str]:
        """A file written moments ago has no row yet, so only what survived the grace window is considered, walked a batch at a time to the last of them."""
        after = 0

        while page := list((await db.execute(self.waiting(after))).scalars()):
            for record in page:
                yield record.key

            after = page[-1].id

    async def discard_orphans(self, db: AsyncSession) -> list[str]:
        discarded = []

        while True:
            waiting = list((await db.execute(self.waiting())).scalars())

            if not waiting:
                return discarded

            batch = []

            # A row is taken only while nothing has named it yet, because a save that named it after it was read would otherwise point at a deleted file.
            for record in waiting:
                if (await db.execute(delete(StoredFile).where(StoredFile.id == record.id, StoredFile.claimed_at.is_(None)))).rowcount == 1:
                    batch.append(record.key)

            await db.commit()

            # The file goes after its row, so a pass cut in half leaves a file no row names rather than a row naming a file that was deleted.
            await upload_service.discard(batch)

            discarded += batch


sweep_service = SweepService()
