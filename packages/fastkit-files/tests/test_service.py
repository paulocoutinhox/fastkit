import pytest
import pytest_asyncio
from sqlalchemy import select

from fastkit_core.app_config import CoreApp
from fastkit_core.errors.exceptions import FastKitError
from fastkit_core.runtime import Runtime
from fastkit_db.app import DbApp
from fastkit_storage.app import StorageApp
from fastkit_files.app import FilesApp
from fastkit_files.models import StorageFile, StorageFileStatus, StorageFileVariant
from fastkit_files.presets import AVATAR_PRESET, ImagePreset, ImageVariantSpec
from fastkit_files.service import StorageFileService


async def _upload(service, image_factory, **kwargs):
    upload = await service.create_upload_session(tenant_id=1, **kwargs)

    return await service.confirm_image_upload(
        upload.id, image_factory(), "photo.png", "image/png"
    )


async def test_full_upload_and_process(service, image_factory, storage):
    record = await _upload(service, image_factory)

    assert record.status == StorageFileStatus.uploaded.value
    assert record.width == 800
    assert record.checksum
    assert await storage.exists(record.object_key)

    processed = await service.process_image(record.id, AVATAR_PRESET)

    assert processed.status == StorageFileStatus.ready.value

    async with service._database.session_factory() as session:
        variants = (await session.execute(select(StorageFileVariant))).scalars().all()

    assert {variant.name for variant in variants} == {"large", "thumb"}


async def test_reprocessing_replaces_variants_idempotently(service, image_factory):
    record = await _upload(service, image_factory)

    await service.process_image(record.id, AVATAR_PRESET)
    await service.process_image(record.id, AVATAR_PRESET)

    async with service._database.session_factory() as session:
        variants = (await session.execute(select(StorageFileVariant))).scalars().all()

    assert sorted(variant.name for variant in variants) == ["large", "thumb"]


async def test_deleting_an_asset_cascades_its_variants(service, image_factory):
    from fastkit_files.models import StorageFile

    record = await _upload(service, image_factory)
    await service.process_image(record.id, AVATAR_PRESET)

    async with service._database.session_factory() as session:
        await session.delete(await session.get(StorageFile, record.id))
        await session.commit()

    async with service._database.session_factory() as session:
        assert (await session.execute(select(StorageFileVariant))).scalars().all() == []


async def test_confirm_rejects_expired_session(service, image_factory, clock):
    upload = await service.create_upload_session(tenant_id=1, ttl_seconds=100)

    clock.advance(200)

    with pytest.raises(FastKitError, match="not usable"):
        await service.confirm_image_upload(
            upload.id, image_factory(), "x.png", "image/png"
        )


async def test_confirm_rejects_bad_mime(service, image_factory):
    upload = await service.create_upload_session(tenant_id=1)

    with pytest.raises(FastKitError, match="not allowed"):
        await service.confirm_image_upload(
            upload.id, image_factory(), "x.png", "application/pdf"
        )


async def test_confirm_rejects_oversized(service, image_factory):
    upload = await service.create_upload_session(tenant_id=1, max_size_bytes=10)

    with pytest.raises(FastKitError, match="maximum allowed size"):
        await service.confirm_image_upload(
            upload.id, image_factory(), "x.png", "image/png"
        )


async def test_confirm_rejects_too_many_pixels(database, storage, clock, image_factory):
    service = StorageFileService(database, storage, clock=clock, max_pixels=100)
    upload = await service.create_upload_session(tenant_id=1)

    with pytest.raises(FastKitError, match="too many pixels"):
        await service.confirm_image_upload(
            upload.id, image_factory(), "x.png", "image/png"
        )


async def test_process_marks_failed_on_error(service, image_factory, monkeypatch):
    record = await _upload(service, image_factory)

    def broken(*args, **kwargs):
        raise RuntimeError("pillow blew up")

    monkeypatch.setattr("fastkit_files.service.process_variant", broken)

    with pytest.raises(FastKitError, match="processing failed"):
        await service.process_image(record.id, AVATAR_PRESET)

    async with service._database.session_factory() as session:
        record = await session.get(StorageFile, record.id)

    assert record.status == StorageFileStatus.failed.value


async def test_process_propagates_fastkit_error(service, image_factory):
    record = await _upload(service, image_factory)
    bad_preset = ImagePreset(
        name="bad",
        variants=[
            ImageVariantSpec(name="v", width=10, height=10, mode="warp", format="png")
        ],
    )

    with pytest.raises(FastKitError, match="unknown resize mode"):
        await service.process_image(record.id, bad_preset)

    async with service._database.session_factory() as session:
        record = await session.get(StorageFile, record.id)

    assert record.status == StorageFileStatus.failed.value


async def test_confirm_upload_stores_any_file(service, storage):
    upload = await service.create_upload_session(tenant_id=1)
    record = await service.confirm_upload(
        upload.id, b"%PDF-1.7 body", "report.PDF", "application/pdf"
    )

    assert record.kind == "file"
    assert record.extension == "pdf"
    assert record.mime_type == "application/pdf"
    assert record.object_key.endswith(".pdf")
    assert await storage.exists(record.object_key)


async def test_confirm_upload_infers_kind_and_defaults_extension(service):
    upload = await service.create_upload_session(tenant_id=1)
    video = await service.confirm_upload(upload.id, b"movie", "clip.mp4", "video/mp4")
    assert video.kind == "video"

    other = await service.create_upload_session(tenant_id=1)
    blob = await service.confirm_upload(other.id, b"blob", "noext", None)
    assert blob.kind == "file"
    assert blob.extension == "bin"
    assert blob.mime_type is None


async def _attach(service, record, owner_id, slot="cover", owner_type="products"):
    await service.link_slot(owner_type, owner_id, slot, record.object_key)


async def test_link_slot_attaches_and_survives_cleanup(
    service, image_factory, storage, clock
):
    record = await _upload(service, image_factory)
    await _attach(service, record, 1)

    clock.advance(200000)
    removed = await service.cleanup_orphans(older_than_seconds=86400)

    assert removed == 0
    assert await service.get(record.id) is not None
    assert await storage.exists(record.object_key)


async def test_link_slot_replacing_a_value_purges_the_old_asset(
    service, image_factory, storage
):
    old = await _upload(service, image_factory)
    new = await _upload(service, image_factory)
    await _attach(service, old, 1)

    await _attach(service, new, 1)

    assert await service.get(old.id) is None
    assert not await storage.exists(old.object_key)
    assert await service.get(new.id) is not None


async def test_link_slot_clearing_a_value_purges_the_asset(
    service, image_factory, storage
):
    record = await _upload(service, image_factory)
    await _attach(service, record, 1)

    await service.link_slot("products", 1, "cover", None)

    assert await service.get(record.id) is None
    assert not await storage.exists(record.object_key)


async def test_link_slot_is_idempotent(service, image_factory):
    record = await _upload(service, image_factory)
    await _attach(service, record, 1)
    await _attach(service, record, 1)

    async with service._database.session_factory() as session:
        from fastkit_files.models import StorageFileReference

        count = (
            (
                await session.execute(
                    select(StorageFileReference).where(
                        StorageFileReference.storage_file_id == record.id
                    )
                )
            )
            .scalars()
            .all()
        )

    assert len(count) == 1
    assert await service.get(record.id) is not None


async def test_link_by_asset_id_reconciles_a_slot(service, image_factory, storage):
    old = await _upload(service, image_factory)
    new = await _upload(service, image_factory)
    await service.link("user", 7, "avatar", old.id)

    await service.link("user", 7, "avatar", new.id)

    assert await service.get(old.id) is None
    assert not await storage.exists(old.object_key)
    assert await service.get(new.id) is not None


async def test_shared_asset_survives_until_the_last_owner_unlinks(
    service, image_factory, storage
):
    record = await _upload(service, image_factory)
    await service.link_slot("products", 1, "cover", record.object_key)
    await service.link_slot("products", 2, "cover", record.object_key)

    await service.unlink_owner("products", 1)
    assert await service.get(record.id) is not None

    await service.unlink_owner("products", 2)
    assert await service.get(record.id) is None
    assert not await storage.exists(record.object_key)


async def test_unlink_owner_purges_variants_too(service, image_factory, storage):
    record = await _upload(service, image_factory)
    await service.process_image(record.id, AVATAR_PRESET)
    await service.link_slot("products", 1, "cover", record.object_key)

    async with service._database.session_factory() as session:
        variants = (
            (
                await session.execute(
                    select(StorageFileVariant).where(
                        StorageFileVariant.storage_file_id == record.id
                    )
                )
            )
            .scalars()
            .all()
        )

    keys = [variant.object_key for variant in variants]

    await service.unlink_owner("products", 1)

    assert await service.get(record.id) is None

    for key in keys:
        assert not await storage.exists(key)


async def test_get_returns_asset_or_none(service, image_factory):
    record = await _upload(service, image_factory)

    assert (await service.get(record.id)).object_key == record.object_key
    assert await service.get(999999) is None


async def test_cleanup_orphans_reaps_unattached(service, image_factory, clock):
    await _upload(service, image_factory)

    clock.advance(200000)
    removed = await service.cleanup_orphans(older_than_seconds=86400)

    assert removed == 1

    async with service._database.session_factory() as session:
        remaining = (await session.execute(select(StorageFile))).scalars().all()

    assert remaining == []


class Settings:
    class app:
        environment = "dev"
        secret_key = "demo-secret"

    class database:
        url = "sqlite+aiosqlite:///:memory:"
        pool_pre_ping = True
        echo = False

    class storage:
        provider = "local"
        root = ""
        base_url = "/media"

    installed_apps = ["fastkit.core", "fastkit.db", "fastkit.storage", "fastkit.files"]


@pytest_asyncio.fixture
async def runtime(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "fastkit_core.runtime.discover_apps",
        lambda: {
            "fastkit.core": CoreApp,
            "fastkit.db": DbApp,
            "fastkit.storage": StorageApp,
            "fastkit.files": FilesApp,
        },
    )
    settings = Settings()
    settings.storage.root = str(tmp_path / "media")

    runtime = Runtime(settings=settings, installed_apps=list(settings.installed_apps))
    runtime.bootstrap()

    yield runtime

    await runtime.stop()


async def test_files_app_registers(runtime):
    assert StorageFile in runtime.models.all()
    assert isinstance(runtime.component("file_service"), StorageFileService)
