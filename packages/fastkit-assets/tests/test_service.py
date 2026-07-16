import pytest
import pytest_asyncio
from sqlalchemy import select

from fastkit_core.app_config import CoreApp
from fastkit_core.errors.exceptions import FastKitError
from fastkit_core.runtime import Runtime
from fastkit_db.app import DbApp
from fastkit_storage.app import StorageApp
from fastkit_assets.app import AssetsApp
from fastkit_assets.models import Asset, AssetStatus, AssetVariant
from fastkit_assets.presets import AVATAR_PRESET, ImagePreset, ImageVariantSpec
from fastkit_assets.service import AssetService


async def _upload(service, image_factory, **kwargs):
    upload = await service.create_upload_session(tenant_id=1, **kwargs)

    return await service.confirm_image_upload(upload.id, image_factory(), "photo.png", "image/png")


async def test_full_upload_and_process(service, image_factory, storage):
    asset = await _upload(service, image_factory)

    assert asset.status == AssetStatus.uploaded.value
    assert asset.width == 800
    assert asset.checksum
    assert await storage.exists(asset.object_key)

    processed = await service.process_image(asset.id, AVATAR_PRESET)

    assert processed.status == AssetStatus.ready.value

    async with service._session_factory() as session:
        variants = (await session.execute(select(AssetVariant))).scalars().all()

    assert {variant.name for variant in variants} == {"large", "thumb"}


async def test_reprocessing_replaces_variants_idempotently(service, image_factory):
    asset = await _upload(service, image_factory)

    await service.process_image(asset.id, AVATAR_PRESET)
    await service.process_image(asset.id, AVATAR_PRESET)

    async with service._session_factory() as session:
        variants = (await session.execute(select(AssetVariant))).scalars().all()

    assert sorted(variant.name for variant in variants) == ["large", "thumb"]


async def test_deleting_an_asset_cascades_its_variants(service, image_factory):
    from fastkit_assets.models import Asset

    asset = await _upload(service, image_factory)
    await service.process_image(asset.id, AVATAR_PRESET)

    async with service._session_factory() as session:
        await session.delete(await session.get(Asset, asset.id))
        await session.commit()

    async with service._session_factory() as session:
        assert (await session.execute(select(AssetVariant))).scalars().all() == []


async def test_confirm_rejects_expired_session(service, image_factory, clock):
    upload = await service.create_upload_session(tenant_id=1, ttl_seconds=100)

    clock.advance(200)

    with pytest.raises(FastKitError, match="not usable"):
        await service.confirm_image_upload(upload.id, image_factory(), "x.png", "image/png")


async def test_confirm_rejects_bad_mime(service, image_factory):
    upload = await service.create_upload_session(tenant_id=1)

    with pytest.raises(FastKitError, match="not allowed"):
        await service.confirm_image_upload(upload.id, image_factory(), "x.png", "application/pdf")


async def test_confirm_rejects_oversized(service, image_factory):
    upload = await service.create_upload_session(tenant_id=1, max_size_bytes=10)

    with pytest.raises(FastKitError, match="maximum allowed size"):
        await service.confirm_image_upload(upload.id, image_factory(), "x.png", "image/png")


async def test_confirm_rejects_too_many_pixels(database, storage, clock, image_factory):
    service = AssetService(database.session_factory, storage, clock=clock, max_pixels=100)
    upload = await service.create_upload_session(tenant_id=1)

    with pytest.raises(FastKitError, match="too many pixels"):
        await service.confirm_image_upload(upload.id, image_factory(), "x.png", "image/png")


async def test_process_marks_failed_on_error(service, image_factory, monkeypatch):
    asset = await _upload(service, image_factory)

    def broken(*args, **kwargs):
        raise RuntimeError("pillow blew up")

    monkeypatch.setattr("fastkit_assets.service.process_variant", broken)

    with pytest.raises(FastKitError, match="processing failed"):
        await service.process_image(asset.id, AVATAR_PRESET)

    async with service._session_factory() as session:
        stored = await session.get(Asset, asset.id)

    assert stored.status == AssetStatus.failed.value


async def test_process_propagates_fastkit_error(service, image_factory):
    asset = await _upload(service, image_factory)
    bad_preset = ImagePreset(name="bad", variants=[ImageVariantSpec(name="v", width=10, height=10, mode="warp", format="png")])

    with pytest.raises(FastKitError, match="unknown resize mode"):
        await service.process_image(asset.id, bad_preset)

    async with service._session_factory() as session:
        stored = await session.get(Asset, asset.id)

    assert stored.status == AssetStatus.failed.value


async def test_attach(service, image_factory):
    asset = await _upload(service, image_factory)

    attachment = await service.attach(asset.id, "User", "42", slot="avatar")

    assert attachment.owner_type == "User"
    assert attachment.owner_id == "42"


async def test_get_returns_asset_or_none(service, image_factory):
    asset = await _upload(service, image_factory)

    assert (await service.get(asset.id)).object_key == asset.object_key
    assert await service.get(999999) is None


async def test_cleanup_orphans(service, image_factory, clock):
    await _upload(service, image_factory)

    clock.advance(200000)
    removed = await service.cleanup_orphans(older_than_seconds=86400)

    assert removed == 1

    async with service._session_factory() as session:
        remaining = (await session.execute(select(Asset))).scalars().all()

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

    installed_apps = ["fastkit.core", "fastkit.db", "fastkit.storage", "fastkit.assets"]


@pytest_asyncio.fixture
async def runtime(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "fastkit_core.runtime.discover_apps",
        lambda: {"fastkit.core": CoreApp, "fastkit.db": DbApp, "fastkit.storage": StorageApp, "fastkit.assets": AssetsApp},
    )
    settings = Settings()
    settings.storage.root = str(tmp_path / "media")

    runtime = Runtime(settings=settings, installed_apps=list(settings.installed_apps))
    runtime.bootstrap()

    yield runtime

    await runtime.stop()


async def test_assets_app_registers(runtime):
    assert Asset in runtime.models.all()
    assert isinstance(runtime.component("asset_service"), AssetService)
