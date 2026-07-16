from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select

from fastkit_core.errors.exceptions import FastKitError
from fastkit_assets.errors import PROCESSING_FAILED, UPLOAD_SESSION_EXPIRED
from fastkit_assets.images import inspect, process_variant, enforce_pixels
from fastkit_assets.models import (
    Asset,
    AssetAttachment,
    AssetKind,
    AssetStatus,
    AssetVariant,
    UploadSession,
    UploadStatus,
)
from fastkit_assets.presets import ImagePreset
from fastkit_assets.security import ALLOWED_IMAGE_MIME, checksum, enforce_mime, enforce_size, random_object_key


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)

    return value


class AssetService:
    """Drives the pseudo-atomic upload and image processing lifecycle."""

    def __init__(self, session_factory, storage, clock=None, max_pixels: int = 40_000_000):
        self._session_factory = session_factory
        self._storage = storage
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._max_pixels = max_pixels

    async def create_upload_session(self, tenant_id: int | None, user_id=None, max_size_bytes: int = 10_000_000, ttl_seconds: int = 3600) -> UploadSession:
        session_row = UploadSession(
            tenant_id=tenant_id,
            user_id=user_id,
            max_size_bytes=max_size_bytes,
            temporary_object_key=random_object_key(tenant_id, "upload"),
            expires_at=self._clock() + timedelta(seconds=ttl_seconds),
        )

        async with self._session_factory() as session:
            session.add(session_row)
            await session.commit()
            await session.refresh(session_row)

            return session_row

    async def confirm_image_upload(self, session_id, data: bytes, filename: str, declared_mime: str) -> Asset:
        async with self._session_factory() as session:
            upload = await session.get(UploadSession, session_id)

            if upload.status != UploadStatus.pending.value or _aware(upload.expires_at) <= self._clock():
                upload.status = UploadStatus.expired.value
                await session.commit()
                raise FastKitError(UPLOAD_SESSION_EXPIRED, message="upload session is not usable")

        enforce_size(data, upload.max_size_bytes)
        enforce_mime(declared_mime, ALLOWED_IMAGE_MIME)

        info = inspect(data)
        enforce_pixels(info, self._max_pixels)

        object_key = random_object_key(upload.tenant_id, info.format.lower())
        await self._storage.put(object_key, data, content_type=info.mime_type)

        asset = Asset(
            tenant_id=upload.tenant_id,
            kind=AssetKind.image.value,
            status=AssetStatus.uploaded.value,
            object_key=object_key,
            original_filename=filename,
            extension=info.format.lower(),
            mime_type=info.mime_type,
            size_bytes=len(data),
            checksum=checksum(data),
            width=info.width,
            height=info.height,
            created_by_id=upload.user_id,
            created_at=self._clock(),
        )

        async with self._session_factory() as session:
            session.add(asset)
            await session.flush()

            stored_upload = await session.get(UploadSession, session_id)
            stored_upload.status = UploadStatus.confirmed.value
            stored_upload.confirmed_at = self._clock()
            stored_upload.asset_id = asset.id

            await session.commit()
            await session.refresh(asset)

            return asset

    async def get(self, asset_id) -> Asset | None:
        async with self._session_factory() as session:
            return await session.get(Asset, asset_id)

    async def process_image(self, asset_id, preset: ImagePreset) -> Asset:
        await self._set_status(asset_id, AssetStatus.processing.value)

        try:
            async with self._session_factory() as session:
                asset = await session.get(Asset, asset_id)
                original = await self._storage.get(asset.object_key)

            for spec in preset.variants:
                variant = process_variant(original, spec)
                variant_key = random_object_key(asset.tenant_id, spec.format)
                await self._storage.put(variant_key, variant.data, content_type=variant.mime_type)

                await self._save_variant(asset_id, spec.name, variant_key, variant)
        except FastKitError:
            await self._set_status(asset_id, AssetStatus.failed.value)
            raise
        except Exception as error:
            await self._set_status(asset_id, AssetStatus.failed.value)
            raise FastKitError(PROCESSING_FAILED, message="image processing failed") from error

        return await self._set_status(asset_id, AssetStatus.ready.value)

    async def attach(self, asset_id, owner_type: str, owner_id: str, slot: str = "default", position: int = 0) -> AssetAttachment:
        attachment = AssetAttachment(asset_id=asset_id, owner_type=owner_type, owner_id=str(owner_id), slot=slot, position=position)

        async with self._session_factory() as session:
            session.add(attachment)
            await session.commit()
            await session.refresh(attachment)

            return attachment

    async def cleanup_orphans(self, older_than_seconds: int = 86400) -> int:
        cutoff = self._clock() - timedelta(seconds=older_than_seconds)
        removed = 0

        async with self._session_factory() as session:
            stale = (
                await session.execute(
                    select(Asset).where(Asset.status == AssetStatus.uploaded.value, Asset.created_at < cutoff)
                )
            ).scalars().all()

            for asset in stale:
                await self._storage.delete(asset.object_key)
                await session.delete(asset)
                removed += 1

            await session.commit()

        return removed

    async def _set_status(self, asset_id, status) -> Asset:
        async with self._session_factory() as session:
            asset = await session.get(Asset, asset_id)
            asset.status = status
            await session.commit()
            await session.refresh(asset)

            return asset

    async def _save_variant(self, asset_id, name, object_key, variant) -> None:
        async with self._session_factory() as session:
            await session.execute(delete(AssetVariant).where(AssetVariant.asset_id == asset_id, AssetVariant.name == name))
            session.add(
                AssetVariant(
                    asset_id=asset_id,
                    name=name,
                    object_key=object_key,
                    format=variant.format,
                    mime_type=variant.mime_type,
                    width=variant.width,
                    height=variant.height,
                    size_bytes=variant.size_bytes,
                )
            )
            await session.commit()
