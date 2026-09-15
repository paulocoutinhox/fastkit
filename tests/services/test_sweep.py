from datetime import timedelta

import pytest
from sqlalchemy import select, update

from enums.upload import UploadPurpose
from helpers.dates import now
from helpers.settings import settings
from helpers.storage import storage
from models.upload import StoredFile
from services.commerce import product_service
from services.seed import seed_service
from services.sweep import sweep_service
from services.upload import upload_service
from tests.routes.test_upload import PNG

STALE = timedelta(days=3)


@pytest.fixture(autouse=True)
def workspace(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "root", tmp_path)


class Incoming:
    """A file the way it reaches the upload service, so a test walks the path an operator walks."""

    def __init__(self, filename: str, content_type: str = "application/epub+zip"):
        self.filename = filename
        self.content_type = content_type
        self.body = PNG if filename.endswith(".png") else b"bytes"

    async def read(self, size: int = -1) -> bytes:
        body, self.body = self.body, b""

        return body


async def uploaded(db, purpose: UploadPurpose = UploadPurpose.PRODUCT_FILE, filename: str = "manual.epub", age: timedelta = STALE) -> str:
    stored = await upload_service.store(db, purpose, Incoming(filename))

    await db.execute(update(StoredFile).where(StoredFile.key == stored["key"]).values(created_at=now() - age))
    await db.commit()

    return stored["key"]


async def test_a_file_nothing_claimed_is_orphan(db):
    key = await uploaded(db)

    assert await sweep_service.find_orphans(db) == [key]


async def test_a_file_a_column_holds_is_kept(db):
    key = await uploaded(db)
    await product_service.create(db, {"name": "The Handbook", "file": key})

    assert await sweep_service.find_orphans(db) == []


async def test_a_file_the_html_of_a_record_embeds_is_kept(db):
    """The editor writes a link inside the markup rather than a key into a column, so what a row mentions is read out of the row itself."""
    key = await uploaded(db, UploadPurpose.IMAGE, "drawing.png")
    await product_service.create(db, {"name": "The Handbook", "description": f'<p>look</p><img src="/media/{key}" alt="">'})

    assert await sweep_service.find_orphans(db) == []


async def test_a_file_the_metadata_of_a_record_mentions_is_kept(db):
    key = await uploaded(db, UploadPurpose.IMAGE, "drawing.png")
    await product_service.create(db, {"name": "The Handbook", "meta": {"gallery": [key]}})

    assert await sweep_service.find_orphans(db) == []


async def test_a_file_written_inside_the_grace_window_is_left_alone(db):
    await uploaded(db, age=timedelta(hours=1))

    assert await sweep_service.find_orphans(db) == []


async def test_a_file_this_application_never_wrote_down_is_never_touched(db):
    """The pass deletes from its own rows, so whatever else lives in the bucket is not its to decide about."""
    await storage.save("files/product/2026/07/29/handwritten.epub", b"bytes", "application/epub+zip")

    assert await sweep_service.find_orphans(db) == []


async def test_discarding_removes_the_orphans_and_keeps_the_rest(db):
    orphan = await uploaded(db)
    kept = await uploaded(db, UploadPurpose.PRODUCT_IMAGE, "drawing.png")

    await product_service.create(db, {"name": "The Handbook", "image": kept})

    assert await sweep_service.discard_orphans(db) == [orphan]
    assert await storage.read(orphan) is None
    assert await storage.read(kept) is not None
    # The row of a file that stays is the only place its uuid answers the key it was written under.
    assert (await db.execute(select(StoredFile.key))).scalars().all() == [kept]


async def test_a_pass_walks_every_batch_and_not_only_the_first(db, monkeypatch):
    """The rows are read in batches so the memory it holds is the batch, and a pass that stopped at one would leave the rest for tomorrow."""
    monkeypatch.setattr("services.sweep.BATCH", 2)

    keys = [await uploaded(db, filename=f"manual-{index}.epub") for index in range(5)]

    assert sorted(await sweep_service.discard_orphans(db)) == sorted(keys)


@pytest.mark.parametrize("grace,expected", [(1, 1), (96, 0)])
async def test_the_grace_window_is_what_the_environment_declares(db, monkeypatch, grace, expected):
    monkeypatch.setattr(settings.storage, "orphan_grace_hours", grace)

    await uploaded(db)

    assert len(await sweep_service.find_orphans(db)) == expected


async def test_the_pass_reads_its_own_rows_and_never_the_whole_of_anything(db):
    """The point of writing a file down is that the pass never grows with the bucket or with the content of the tables."""
    from sqlalchemy import event

    from helpers.db import async_engine

    await uploaded(db)
    await product_service.create(db, {"name": "The Handbook", "description": "<p>a body</p>"})

    read = []
    watch = lambda *arguments: read.append(str(arguments[2]))  # noqa: E731

    event.listen(async_engine.sync_engine, "before_cursor_execute", watch)

    try:
        await sweep_service.find_orphans(db)
    finally:
        event.remove(async_engine.sync_engine, "before_cursor_execute", watch)

    scanned = [statement for statement in read if "FROM" in statement and "stored_file" not in statement]

    assert read, "the pass issued nothing at all, so it is proving nothing"
    assert scanned == [], f"the pass read a table that is not its own: {scanned}"
    assert all("LIMIT" in statement for statement in read if "stored_file" in statement), "the pass reads its rows without a batch"


async def test_a_seeded_picture_is_spoken_for_the_moment_it_lands(db):
    """The seed writes its rows without the factory, so the picture is claimed where it is stored or the pass would collect what a seeded page shows."""
    await seed_service.photograph(db, UploadPurpose.BANNER, "banner-welcome.jpg", "Welcome")

    await db.execute(update(StoredFile).values(created_at=now() - STALE))
    await db.commit()

    assert await sweep_service.find_orphans(db) == []


async def test_a_file_that_never_landed_leaves_a_row_the_pass_clears(db, monkeypatch):
    """A write that fails after the file is written down leaves a row naming nothing, which the pass takes, and never a file nothing wrote down."""

    async def refuse(key, payload, content_type):
        raise OSError("the disk said no")

    monkeypatch.setattr("helpers.storage.storage.save", refuse)

    with pytest.raises(OSError):
        await upload_service.store(db, UploadPurpose.PRODUCT_FILE, Incoming("manual.epub"))

    await db.execute(update(StoredFile).values(created_at=now() - STALE))
    await db.commit()

    assert len(await sweep_service.discard_orphans(db)) == 1
    assert (await db.execute(select(StoredFile.key))).scalars().all() == []
