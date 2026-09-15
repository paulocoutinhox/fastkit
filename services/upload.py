import asyncio
import logging
import mimetypes
import os
from io import BytesIO
from tempfile import SpooledTemporaryFile
from typing import Protocol

from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import delete, exists, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from config.base import ImageSettings, UploadSettings
from enums.upload import ImageFormat, UploadPurpose
from helpers.dates import now
from helpers.db import insert_or_read
from helpers.errors import ConflictError, ValidationError
from helpers.settings import settings
from helpers.storage import build_key, storage, uuids_in
from models.upload import StoredFile, StoredFileMention


def owner_of(instance) -> str:
    """The name a row mentions a file under, which is its table and its id."""
    return f"{instance.__tablename__}:{instance.id}"


def named_in(values) -> set[str]:
    """Which stored files a set of values names, read the same way whether a caller holds a key, a body of markup or the uuid itself."""
    return set().union(*(uuids_in(value) for value in values if value is not None)) if values else set()


class IncomingFile(Protocol):
    """What storing a file actually needs, so this layer never depends on how the bytes arrived."""

    filename: str | None

    async def read(self, size: int = -1) -> bytes: ...


MEGABYTE = 1024 * 1024

SPOOL = 4 * MEGABYTE

CHUNK = 64 * 1024

IMAGE_FORMAT_EXTENSIONS = {ImageFormat.JPEG: ".jpg", ImageFormat.PNG: ".png", ImageFormat.WEBP: ".webp"}

logger = logging.getLogger(__name__)

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
        filename = upload.filename
        payload = body

        if rule.image is not None:
            payload, filename, size = await asyncio.to_thread(self.settle_image, body.read(), rule.image, filename)

        key = build_key(rule.folder, filename, rule.naming)

        # The bucket serves a file with the type it was stored under, so the type is the one the checked extension names and never what the caller claimed.
        content_type = mimetypes.guess_type(key)[0]

        # The file is written down before it is written, because a row naming nothing is swept and a file nothing wrote down is never seen again.
        db.add(StoredFile(uuid=uuids_in(key).pop(), key=key, purpose=purpose, size=size))
        await db.commit()

        await storage.save(key, payload, content_type)

        return {"key": key, "url": storage.url(key), "size": size}

    async def mention(self, db: AsyncSession, owner: str, values, keys=()) -> set[str]:
        """Writes which stored files a row names now, in the transaction of the row, and answers the ones it stopped naming, read from what was written down and never from a row in memory another request may have moved on from."""
        named = named_in(values)
        held = dict((await db.execute(select(StoredFile.uuid, StoredFileMention.id).join(StoredFileMention, StoredFileMention.stored_file_id == StoredFile.id).where(StoredFileMention.owner == owner))).all())
        dropped = set(held) - named
        added = named - set(held)

        if dropped:
            await db.execute(delete(StoredFileMention).where(StoredFileMention.id.in_([held[uuid] for uuid in dropped])))

        if not added:
            return dropped

        # A file named once is one the sweep of what nothing ever named leaves alone for good, and the stamp moves on every new name so a release that read the old one waits and then finds it changed.
        await db.execute(update(StoredFile).where(StoredFile.uuid.in_(added)).values(claimed_at=now()))

        found = dict((await db.execute(select(StoredFile.uuid, StoredFile.id).where(StoredFile.uuid.in_(added)))).all())

        # A file column holds a key and nothing else, so one whose file went before this write, a form left open past the grace of the sweep, draws nothing, and one that borrows another file's uuid under a made-up path would pin that file while drawing nothing too.
        fresh = {key for key in keys if uuids_in(key) & added}

        if fresh - set((await db.execute(select(StoredFile.key).where(StoredFile.key.in_(fresh)))).scalars()):
            raise ConflictError("error.file-gone")

        for stored_file_id in found.values():
            written = await insert_or_read(db, StoredFileMention(stored_file_id=stored_file_id, owner=owner), select(StoredFileMention).where(StoredFileMention.stored_file_id == stored_file_id, StoredFileMention.owner == owner))

            # A file released by another request between the read and the insert is gone, and saving a row that names it would point at nothing.
            if written is None:
                raise ConflictError("error.file-gone")

        return dropped

    async def forget(self, db: AsyncSession, owners) -> set[str]:
        """Drops what the owners named, read from what was written down, and answers those files so the caller releases them once the owners are gone."""
        written = (await db.execute(select(StoredFile.uuid, StoredFileMention.id).join(StoredFileMention, StoredFileMention.stored_file_id == StoredFile.id).where(StoredFileMention.owner.in_(owners)))).all()

        if written:
            await db.execute(delete(StoredFileMention).where(StoredFileMention.id.in_([mention for _uuid, mention in written])))

        return {uuid for uuid, _mention in written}

    async def release(self, db: AsyncSession, values) -> None:
        """Discards the files a row stopped naming, unless another row still names them, wherever the key was pasted."""
        uuids = named_in(values)

        if not uuids:
            return

        unnamed = ~exists().where(StoredFileMention.stored_file_id == StoredFile.id)
        discarded = []

        # The row goes before the file and only while nothing names it, because a file deleted first is gone for a row that named it a moment later.
        # A name written while this waited is invisible to the check beside it, and the stamp on the row itself is what the database reads again once the wait is over.
        for record in list((await db.execute(select(StoredFile).where(StoredFile.uuid.in_(uuids)))).scalars()):
            if (await db.execute(delete(StoredFile).where(StoredFile.id == record.id, StoredFile.claimed_at == record.claimed_at, unnamed))).rowcount == 1:
                discarded.append(record.key)

        await db.commit()

        await self.discard(discarded)

    async def discard(self, keys: list[str]) -> None:
        """Deletes files whose rows are already gone, where one the storage refuses is left over and written down, and never takes the others or the request with it."""
        for key in keys:
            try:
                await storage.delete(key)
            except Exception:
                logger.exception("[storage] %s outlived its row, and the storage refused to delete it", key)

    def settle_image(self, data: bytes, rule: ImageSettings, filename: str) -> tuple[bytes, str, int]:
        """The bytes are decoded either way, because an extension is what a name claims and never what the content is."""
        image = self.open_image(data)

        if rule.store == "original":
            return data, filename, len(data)

        processed, extension = self.process_image(image, rule)

        return processed, f"{os.path.splitext(filename)[0]}{extension}", len(processed)

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

            # A phone stores a portrait sideways and says so in its orientation tag, which the encoding drops, and a broken tag is a broken file like any other.
            return ImageOps.exif_transpose(image)
        # A PNG whose chunks break after the pixels raises the decoder's own SyntaxError, which is how Pillow says a file is broken.
        except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as error:
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

    def process_image(self, image: Image.Image, rule: ImageSettings) -> tuple[bytes, str]:
        resized = self.resize(image, rule)

        if rule.image_format is ImageFormat.JPEG and resized.mode != "RGB":
            resized = resized.convert("RGB")

        buffer = BytesIO()
        options = {"quality": rule.quality, "optimize": True} if rule.image_format in (ImageFormat.JPEG, ImageFormat.WEBP) else {"optimize": True}
        resized.save(buffer, rule.image_format.upper(), **options)

        return buffer.getvalue(), IMAGE_FORMAT_EXTENSIONS[rule.image_format]


upload_service = UploadService()
