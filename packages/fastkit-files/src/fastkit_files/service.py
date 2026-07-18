from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import delete, func, select

from fastkit_core.errors.exceptions import FastKitError
from fastkit_files.errors import PROCESSING_FAILED, UPLOAD_SESSION_EXPIRED
from fastkit_files.images import inspect, process_variant, enforce_pixels
from fastkit_files.models import (
    StorageFile,
    StorageFileReference,
    StorageFileKind,
    StorageFileStatus,
    StorageFileVariant,
    UploadSession,
    UploadStatus,
)
from fastkit_files.presets import ImagePreset
from fastkit_files.security import ALLOWED_IMAGE_MIME, checksum, enforce_mime, enforce_size, random_object_key


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)

    return value


def _extension(filename: str | None) -> str:
    suffix = Path(filename or "").suffix.lstrip(".").lower()

    return suffix or "bin"


def _kind_for(content_type: str | None) -> str:
    main = (content_type or "").split("/", 1)[0]
    mapping = {"image": StorageFileKind.image.value, "video": StorageFileKind.video.value, "audio": StorageFileKind.audio.value}

    return mapping.get(main, StorageFileKind.file.value)


class StorageFileService:
    """Drives the pseudo-atomic upload and image processing lifecycle."""

    def __init__(self, database, storage, clock=None, max_pixels: int = 40_000_000):
        self._database = database
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

        async with self._database.session_factory() as session:
            session.add(session_row)
            await session.commit()
            await session.refresh(session_row)

            return session_row

    async def confirm_image_upload(self, session_id, data: bytes, filename: str, declared_mime: str) -> StorageFile:
        upload = await self._reserve_upload(session_id)
        enforce_size(data, upload.max_size_bytes)
        enforce_mime(declared_mime, ALLOWED_IMAGE_MIME)

        info = inspect(data)
        enforce_pixels(info, self._max_pixels)

        object_key = random_object_key(upload.tenant_id, info.format.lower())
        await self._storage.put(object_key, data, content_type=info.mime_type)

        record = StorageFile(
            tenant_id=upload.tenant_id,
            kind=StorageFileKind.image.value,
            status=StorageFileStatus.uploaded.value,
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

        return await self._persist(session_id, record)

    async def confirm_upload(self, session_id, data: bytes, filename: str, content_type: str | None) -> StorageFile:
        upload = await self._reserve_upload(session_id)
        enforce_size(data, upload.max_size_bytes)

        extension = _extension(filename)
        object_key = random_object_key(upload.tenant_id, extension)
        await self._storage.put(object_key, data, content_type=content_type or "application/octet-stream")

        record = StorageFile(
            tenant_id=upload.tenant_id,
            kind=_kind_for(content_type),
            status=StorageFileStatus.uploaded.value,
            object_key=object_key,
            original_filename=filename,
            extension=extension,
            mime_type=content_type,
            size_bytes=len(data),
            checksum=checksum(data),
            created_by_id=upload.user_id,
            created_at=self._clock(),
        )

        return await self._persist(session_id, record)

    async def _reserve_upload(self, session_id) -> UploadSession:
        async with self._database.session_factory() as session:
            upload = await session.get(UploadSession, session_id)

            if upload.status != UploadStatus.pending.value or _aware(upload.expires_at) <= self._clock():
                upload.status = UploadStatus.expired.value
                await session.commit()
                raise FastKitError(UPLOAD_SESSION_EXPIRED, message="upload session is not usable")

            return upload

    async def _persist(self, session_id, record: StorageFile) -> StorageFile:
        async with self._database.session_factory() as session:
            session.add(record)
            await session.flush()

            stored_upload = await session.get(UploadSession, session_id)
            stored_upload.status = UploadStatus.confirmed.value
            stored_upload.confirmed_at = self._clock()
            stored_upload.storage_file_id = record.id

            await session.commit()
            await session.refresh(record)

            return record

    async def get(self, storage_file_id) -> StorageFile | None:
        async with self._database.session_factory() as session:
            return await session.get(StorageFile, storage_file_id)

    async def process_image(self, storage_file_id, preset: ImagePreset) -> StorageFile:
        await self._set_status(storage_file_id, StorageFileStatus.processing.value)

        try:
            async with self._database.session_factory() as session:
                record = await session.get(StorageFile, storage_file_id)
                original = await self._storage.get(record.object_key)

            for spec in preset.variants:
                variant = process_variant(original, spec)
                variant_key = random_object_key(record.tenant_id, spec.format)
                await self._storage.put(variant_key, variant.data, content_type=variant.mime_type)

                await self._save_variant(storage_file_id, spec.name, variant_key, variant)
        except FastKitError:
            await self._set_status(storage_file_id, StorageFileStatus.failed.value)
            raise
        except Exception as error:
            await self._set_status(storage_file_id, StorageFileStatus.failed.value)
            raise FastKitError(PROCESSING_FAILED, message="image processing failed") from error

        return await self._set_status(storage_file_id, StorageFileStatus.ready.value)

    async def link_slot(self, owner_type: str, owner_id, slot: str, object_key: str | None) -> None:
        async with self._database.session_factory() as session:
            target = None

            if object_key:
                target = (await session.execute(select(StorageFile).where(StorageFile.object_key == object_key))).scalar_one_or_none()

            await self._reconcile_slot(session, owner_type, owner_id, slot, target.id if target is not None else None)
            await session.commit()

    async def link(self, owner_type: str, owner_id, slot: str, storage_file_id) -> None:
        async with self._database.session_factory() as session:
            await self._reconcile_slot(session, owner_type, owner_id, slot, storage_file_id)
            await session.commit()

    async def unlink_owner(self, owner_type: str, owner_id) -> None:
        async with self._database.session_factory() as session:
            attachments = (
                await session.execute(
                    select(StorageFileReference).where(
                        StorageFileReference.owner_type == owner_type,
                        StorageFileReference.owner_id == str(owner_id),
                    )
                )
            ).scalars().all()

            asset_ids = {attachment.storage_file_id for attachment in attachments}

            for attachment in attachments:
                await session.delete(attachment)

            await session.flush()

            for storage_file_id in asset_ids:
                await self._purge_if_orphaned(session, storage_file_id)

            await session.commit()

    async def cleanup_orphans(self, older_than_seconds: int = 86400) -> int:
        cutoff = self._clock() - timedelta(seconds=older_than_seconds)
        attached = select(StorageFileReference.id).where(StorageFileReference.storage_file_id == StorageFile.id).exists()

        async with self._database.session_factory() as session:
            stale = (
                await session.execute(select(StorageFile).where(StorageFile.created_at < cutoff, ~attached))
            ).scalars().all()

            for record in stale:
                await self._purge(session, record)

            await session.commit()

        return len(stale)

    async def _reconcile_slot(self, session, owner_type: str, owner_id, slot: str, target_id) -> None:
        current = (
            await session.execute(
                select(StorageFileReference).where(
                    StorageFileReference.owner_type == owner_type,
                    StorageFileReference.owner_id == str(owner_id),
                    StorageFileReference.slot == slot,
                )
            )
        ).scalars().all()

        detached = []
        keep = False

        for attachment in current:
            if attachment.storage_file_id == target_id:
                keep = True
            else:
                detached.append(attachment.storage_file_id)
                await session.delete(attachment)

        if target_id is not None and not keep:
            session.add(StorageFileReference(storage_file_id=target_id, owner_type=owner_type, owner_id=str(owner_id), slot=slot))

        await session.flush()

        for storage_file_id in detached:
            await self._purge_if_orphaned(session, storage_file_id)

    async def _purge_if_orphaned(self, session, storage_file_id) -> None:
        remaining = (
            await session.execute(select(func.count()).select_from(StorageFileReference).where(StorageFileReference.storage_file_id == storage_file_id))
        ).scalar_one()

        if remaining:
            return

        record = await session.get(StorageFile, storage_file_id)
        await self._purge(session, record)

    async def _purge(self, session, record) -> None:
        variants = (await session.execute(select(StorageFileVariant).where(StorageFileVariant.storage_file_id == record.id))).scalars().all()

        for variant in variants:
            await self._storage.delete(variant.object_key)

        await self._storage.delete(record.object_key)
        await session.delete(record)

    async def _set_status(self, storage_file_id, status) -> StorageFile:
        async with self._database.session_factory() as session:
            record = await session.get(StorageFile, storage_file_id)
            record.status = status
            await session.commit()
            await session.refresh(record)

            return record

    async def _save_variant(self, storage_file_id, name, object_key, variant) -> None:
        async with self._database.session_factory() as session:
            await session.execute(delete(StorageFileVariant).where(StorageFileVariant.storage_file_id == storage_file_id, StorageFileVariant.name == name))
            session.add(
                StorageFileVariant(
                    storage_file_id=storage_file_id,
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
