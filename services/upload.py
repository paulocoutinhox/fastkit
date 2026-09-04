import asyncio
import os
from io import BytesIO
from tempfile import SpooledTemporaryFile
from typing import Protocol

from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from config.base import ImageSettings, UploadSettings
from enums.upload import UploadPurpose
from helpers.dates import now
from helpers.errors import ValidationError
from helpers.settings import settings
from helpers.storage import build_key, storage, uuids_in
from models.upload import StoredFile


def named_in(values) -> set[str]:
    """Which stored files a set of values names, read the same way whether a caller holds a key, a body of markup or the uuid itself."""
    return set().union(*(uuids_in(value) for value in values if value is not None)) if values else set()


class IncomingFile(Protocol):
    """What storing a file actually needs, so this layer never depends on how the bytes arrived."""

    filename: str | None
    content_type: str | None

    async def read(self, size: int = -1) -> bytes: ...


MEGABYTE = 1024 * 1024

SPOOL = 4 * MEGABYTE

CHUNK = 64 * 1024

IMAGE_FORMAT_EXTENSIONS = {"jpeg": ".jpg", "png": ".png", "webp": ".webp"}

# The decoder warns rather than refuses up to twice a ceiling of its own, so the exact one is this side's and is checked before anything is allocated.
Image.MAX_IMAGE_PIXELS = None


class UploadService:
    """Every stored file goes through here, so the same rules apply whatever the backing provider is."""

    def rule_for(self, purpose: UploadPurpose) -> UploadSettings:
        """What this environment declares for that purpose, which is the one place the folder, the limits and the shape are read from."""
        return settings.uploads[purpose]

    async def store(self, db: AsyncSession, purpose: UploadPurpose, upload: IncomingFile) -> dict:
        rule = self.rule_for(purpose)
        extension = os.path.splitext(upload.filename or "")[1].lower()

        if extension not in rule.extensions:
            raise ValidationError("error.upload-type-not-allowed", "file")

        # The purpose says what it takes and the environment says what it will hold at all, so the tighter of the two is the one that answers.
        body, size = await self.spool_within(upload, min(rule.max_bytes, settings.upload_max_bytes))

        # The spool is a file on disk past a few megabytes, and it is released here rather than whenever the collector gets to it.
        try:
            if not size:
                raise ValidationError("error.upload-empty", "file")

            return await self.keep(db, purpose, rule, upload, body, size)
        finally:
            body.close()

    async def keep(self, db: AsyncSession, purpose: UploadPurpose, rule: UploadSettings, upload: IncomingFile, body: SpooledTemporaryFile, size: int) -> dict:
        content_type = upload.content_type or "application/octet-stream"
        filename = upload.filename or "file"
        payload = body

        if rule.image is not None:
            payload, filename, content_type, size = await asyncio.to_thread(self.settle_image, body.read(), rule.image, filename, content_type)

        key = build_key(rule.folder, filename, rule.naming)

        # The file is written down before it is written, because a row naming nothing is swept and a file nothing wrote down is never seen again.
        db.add(StoredFile(uuid=uuids_in(key).pop(), key=key, purpose=purpose, size=size))
        await db.commit()

        await storage.save(key, payload, content_type)

        return {"key": key, "url": storage.url(key), "size": size}

    async def claim(self, db: AsyncSession, values) -> None:
        """A file a row mentions is one nobody has to sweep, and the row of it stays as the only place a uuid answers the key it was written under."""
        named = named_in(values)

        if named:
            await db.execute(update(StoredFile).where(StoredFile.uuid.in_(named), StoredFile.claimed_at.is_(None)).values(claimed_at=now()))

    async def release(self, db: AsyncSession, values) -> None:
        """A file the row that mentioned it stopped mentioning, discarded where the mention went instead of left for a pass to notice."""
        named = named_in(values)

        if not named:
            return

        stored = list((await db.execute(select(StoredFile).where(StoredFile.uuid.in_(named)))).scalars())

        for record in stored:
            await storage.delete(record.key)

        # The row goes with the file in a write of its own, because whatever freed it is settled by the time this runs.
        await db.execute(delete(StoredFile).where(StoredFile.id.in_([record.id for record in stored])))
        await db.commit()

    def settle_image(self, data: bytes, rule: ImageSettings, filename: str, content_type: str) -> tuple[bytes, str, str, int]:
        """The bytes are decoded either way, because an extension is what a name claims and never what the content is."""
        image = self.open_image(data)

        if rule.store == "original":
            return data, filename, content_type, len(data)

        processed, extension, kind = self.process_image(image, rule)

        return processed, f"{os.path.splitext(filename)[0]}{extension}", kind, len(processed)

    async def spool_within(self, upload: IncomingFile, limit: int) -> tuple[SpooledTemporaryFile, int]:
        """A file rolls to disk past a few megabytes, so an upload the size of an audiobook never sits whole in the memory of the process."""
        body = SpooledTemporaryFile(max_size=SPOOL)
        total = 0

        while chunk := await upload.read(CHUNK):
            total += len(chunk)

            if total > limit:
                body.close()

                raise ValidationError("error.upload-too-large", "file")

            body.write(chunk)

        body.seek(0)

        return body, total

    def open_image(self, data: bytes) -> Image.Image:
        """An extension is what the name claims and not what the bytes are, so the content is decoded first."""
        try:
            image = Image.open(BytesIO(data))

            # Opening reads the header alone, so the canvas it names is refused before a single pixel of it is allocated.
            if image.width * image.height > settings.image_max_pixels:
                raise ValidationError("error.upload-image-too-large", "file", pixels=settings.image_max_pixels)

            image.load()

            return image
        except (UnidentifiedImageError, OSError, ValueError) as error:
            raise ValidationError("error.upload-not-an-image", "file") from error

    def resize(self, image: Image.Image, rule: ImageSettings) -> Image.Image:
        if rule.width is None and rule.height is None:
            return image

        if rule.crop and rule.width and rule.height:
            return ImageOps.fit(image, (rule.width, rule.height), Image.Resampling.LANCZOS, centering=(0.5, 0.5))

        # A side left out follows the other one, and an image already smaller is never blown up.
        width = rule.width or image.width
        height = rule.height or image.height
        copy = image.copy()
        copy.thumbnail((width, height), Image.Resampling.LANCZOS)

        return copy

    def process_image(self, image: Image.Image, rule: ImageSettings) -> tuple[bytes, str, str]:
        resized = self.resize(image, rule)

        if rule.image_format == "jpeg" and resized.mode != "RGB":
            resized = resized.convert("RGB")

        buffer = BytesIO()
        options = {"quality": rule.quality, "optimize": True} if rule.image_format in ("jpeg", "webp") else {"optimize": True}
        resized.save(buffer, rule.image_format.upper(), **options)

        return buffer.getvalue(), IMAGE_FORMAT_EXTENSIONS[rule.image_format], f"image/{rule.image_format}"


upload_service = UploadService()
