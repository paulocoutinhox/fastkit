from datetime import timedelta

import pytest
from sqlalchemy import select, update

from enums.upload import UploadPurpose
from helpers.dates import now
from helpers.errors import ConflictError
from helpers.settings import settings
from helpers.storage import storage
from models.upload import StoredFile
from services.commerce import product_service
from services.seed import seed_service
from services.sweep import sweep_service
from services.upload import upload_service
from tests.conftest import stored_bytes
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

    assert [key async for key in sweep_service.find_orphans(db)] == [key]


async def test_a_file_a_column_holds_is_kept(db):
    key = await uploaded(db)
    await product_service.create(db, {"name": "The Handbook", "file": key})

    assert [key async for key in sweep_service.find_orphans(db)] == []


async def test_a_file_the_html_of_a_record_embeds_is_kept(db):
    """The editor writes a link inside the markup rather than a key into a column, so what a row mentions is read out of the row itself."""
    key = await uploaded(db, UploadPurpose.IMAGE, "drawing.png")
    await product_service.create(db, {"name": "The Handbook", "description": f'<p>look</p><img src="/media/{key}" alt="">'})

    assert [key async for key in sweep_service.find_orphans(db)] == []


async def test_a_file_the_metadata_of_a_record_mentions_is_kept(db):
    key = await uploaded(db, UploadPurpose.IMAGE, "drawing.png")
    await product_service.create(db, {"name": "The Handbook", "meta": {"gallery": [key]}})

    assert [key async for key in sweep_service.find_orphans(db)] == []


async def test_a_file_written_inside_the_grace_window_is_left_alone(db):
    await uploaded(db, age=timedelta(hours=1))

    assert [key async for key in sweep_service.find_orphans(db)] == []


async def test_a_file_this_application_never_wrote_down_is_never_touched(db):
    """The pass deletes from its own rows, so whatever else lives in the bucket is not its to decide about."""
    await storage.save("files/product/2026/07/29/handwritten.epub", b"bytes", "application/epub+zip")

    assert [key async for key in sweep_service.find_orphans(db)] == []


async def test_discarding_removes_the_orphans_and_keeps_the_rest(db):
    orphan = await uploaded(db)
    kept = await uploaded(db, UploadPurpose.PRODUCT_IMAGE, "drawing.png")

    await product_service.create(db, {"name": "The Handbook", "image": kept})

    assert await sweep_service.discard_orphans(db) == [orphan]
    assert stored_bytes(orphan) is None
    assert stored_bytes(kept) is not None
    # The row of a file that stays is the only place its uuid answers the key it was written under.
    assert (await db.execute(select(StoredFile.key))).scalars().all() == [kept]


async def test_the_listing_walks_every_batch_and_not_only_the_first(db, monkeypatch):
    """A dry run that stopped at the first batch would report a thousand orphans whatever the bucket held."""
    monkeypatch.setattr("services.sweep.BATCH", 2)

    keys = [await uploaded(db, filename=f"manual-{index}.epub") for index in range(5)]

    assert [key async for key in sweep_service.find_orphans(db)] == keys


async def test_a_pass_walks_every_batch_and_not_only_the_first(db, monkeypatch):
    """The rows are read in batches so the memory it holds is the batch, and a pass that stopped at one would leave the rest for tomorrow."""
    monkeypatch.setattr("services.sweep.BATCH", 2)

    keys = [await uploaded(db, filename=f"manual-{index}.epub") for index in range(5)]

    assert sorted(await sweep_service.discard_orphans(db)) == sorted(keys)


@pytest.mark.parametrize("grace,expected", [(1, 1), (96, 0)])
async def test_the_grace_window_is_what_the_environment_declares(db, monkeypatch, grace, expected):
    monkeypatch.setattr(settings.storage, "orphan_grace_hours", grace)

    await uploaded(db)

    assert len([key async for key in sweep_service.find_orphans(db)]) == expected


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
        [key async for key in sweep_service.find_orphans(db)]
    finally:
        event.remove(async_engine.sync_engine, "before_cursor_execute", watch)

    scanned = [statement for statement in read if "FROM" in statement and "stored_file" not in statement]

    assert read, "the pass issued nothing at all, so it is proving nothing"
    assert scanned == [], f"the pass read a table that is not its own: {scanned}"
    assert all("LIMIT" in statement for statement in read if "stored_file" in statement), "the pass reads its rows without a batch"


async def test_a_seeded_picture_is_spoken_for_once_the_seed_writes_down_what_its_rows_name(db):
    """The seed writes its rows without the factory, so what they name is written down from the same declaration or the pass would collect what a seeded page shows."""
    from models.banner import Banner
    from tests.factories import save

    key = await seed_service.photograph(db, UploadPurpose.BANNER, "banner-welcome.jpg", "Welcome")
    await save(db, Banner(title="Welcome", image=key, meta={}))

    await seed_service.mention_pictures(db)
    await db.execute(update(StoredFile).values(created_at=now() - STALE))
    await db.commit()

    assert [key async for key in sweep_service.find_orphans(db)] == []


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


async def test_a_file_released_between_the_read_and_the_mention_refuses_the_row(db, monkeypatch):
    """The row would otherwise be saved naming a file nothing keeps, and the next sweep of it would delete what a page draws."""
    key = await uploaded(db)

    async def gone(session, instance, read):
        return None

    monkeypatch.setattr("services.upload.insert_or_read", gone)

    with pytest.raises(ConflictError) as refused:
        await product_service.create(db, {"name": "The Handbook", "file": key})

    assert refused.value.code == "error.file-gone"


async def test_an_edit_that_loses_the_race_for_a_key_answers_a_conflict_and_names_no_file(db, monkeypatch):
    """Two edits can both pass the check for a free slug, and the flush is what meets the unique key before anything is written down about the files of the row."""
    await product_service.create(db, {"name": "Taken", "slug": "taken"})
    edited = await product_service.create(db, {"name": "Free", "slug": "free"})
    key = await uploaded(db)

    async def passed(*arguments):
        return None

    monkeypatch.setattr(product_service, "ensure_unique", passed)

    with pytest.raises(ConflictError) as refused:
        await product_service.update(db, edited.id, {"slug": "taken", "file": key})

    assert refused.value.code == "error.duplicated-record"
    assert [key async for key in sweep_service.find_orphans(db)] == [key]


async def test_a_file_column_naming_a_file_the_sweep_already_took_refuses_the_row(db):
    """A form left open past the grace of the sweep would otherwise save a record that draws nothing."""
    key = await uploaded(db)
    await sweep_service.discard_orphans(db)

    with pytest.raises(ConflictError) as refused:
        await product_service.create(db, {"name": "The Handbook", "file": key})

    assert refused.value.code == "error.file-gone"


async def test_a_file_column_borrowing_another_files_uuid_under_a_made_up_path_refuses_the_row(db):
    """The column is conferred by its key and not only by the uuid inside it, or a path that draws nothing would pin a file it does not name."""
    key = await uploaded(db)
    from helpers.storage import uuids_in

    borrowed = f"files/product/2020/01/01/{uuids_in(key).pop()}/other.epub"

    with pytest.raises(ConflictError) as refused:
        await product_service.create(db, {"name": "The Handbook", "file": borrowed})

    assert refused.value.code == "error.file-gone"


async def test_a_uuid_written_in_free_text_names_no_file_and_never_refuses_the_row(db):
    """Markup and metadata can carry a uuid that is somebody's order number, so only a file column is held to naming a file."""
    created = await product_service.create(db, {"name": "The Handbook", "meta": {"order": "7f1c2b40-1d5e-4a8e-9b1f-2d3c4e5f6a7b"}})

    assert created.id is not None


async def test_a_file_named_again_while_its_release_waited_stays(db, monkeypatch):
    """Under InnoDB the check that nothing names it was read before the wait, so the stamp on the row itself is what decides once the wait is over."""
    key = await uploaded(db)
    execute = db.execute

    async def racing(statement, *arguments, **options):
        answer = await execute(statement, *arguments, **options)

        # The other request's name lands between the read of the candidates and the delete.
        if getattr(statement, "is_select", False) and StoredFile.__table__ in statement.get_final_froms():
            await execute(update(StoredFile).where(StoredFile.key == key).values(claimed_at=now() + timedelta(seconds=1)).execution_options(synchronize_session=False))

        return answer

    monkeypatch.setattr(db, "execute", racing)

    await upload_service.release(db, [key])

    assert stored_bytes(key) is not None


async def test_a_file_the_storage_refuses_to_delete_is_left_over_and_never_takes_the_rest(db, monkeypatch, caplog):
    """The rows are already gone, so a transient refusal leaves that one file over and is written down, where a raise would answer an error for a save that happened and stop the rest."""
    from helpers.storage import storage
    from services.upload import upload_service

    deleted = []

    async def refusing_the_first(key):
        if not deleted and key == "images/a.webp":
            deleted.append(None)

            raise OSError("the bucket did not answer")

        deleted.append(key)

    monkeypatch.setattr(storage, "delete", refusing_the_first)

    with caplog.at_level("ERROR", logger="services.upload"):
        await upload_service.discard(["images/a.webp", "images/b.webp"])

    assert deleted == [None, "images/b.webp"]
    assert "images/a.webp" in caplog.text
