from datetime import timedelta
from uuid import uuid4

from sqlalchemy import update

from enums.upload import UploadPurpose
from helpers.dates import now
from helpers.settings import settings
from helpers.storage import storage, uuids_in
from jobs.storage import discard_orphan_files
from models.upload import StoredFile


async def stale_file(db) -> str:
    """A file this application wrote down and nothing ever claimed, aged past the grace window."""
    key = f"images/gallery/2026/07/29/{uuid4()}.webp"

    await storage.save(key, b"bytes", "image/webp")

    db.add(StoredFile(uuid=uuids_in(key).pop(), key=key, purpose=UploadPurpose.GALLERY_PHOTO, size=5))
    await db.commit()
    await db.execute(update(StoredFile).where(StoredFile.key == key).values(created_at=now() - timedelta(days=3)))
    await db.commit()

    return key


async def test_the_job_leaves_the_files_alone_where_the_environment_says_not_to_sweep(db, monkeypatch, tmp_path):
    monkeypatch.setattr(storage, "root", tmp_path)
    monkeypatch.setattr(settings.storage, "sweep_orphans", False)

    key = await stale_file(db)

    await discard_orphan_files()

    assert await storage.read(key) is not None


async def test_the_job_discards_what_nothing_claimed(db, monkeypatch, tmp_path):
    monkeypatch.setattr(storage, "root", tmp_path)
    monkeypatch.setattr(settings.storage, "sweep_orphans", True)

    key = await stale_file(db)

    await discard_orphan_files()

    assert await storage.read(key) is None
