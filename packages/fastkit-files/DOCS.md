# fastkit-files

The managed-file layer for FastKit, backed by fastkit-storage: a stored file plus
its metadata and the record(s) that reference it. Generic over any file kind
(`StorageFileKind` = file/image/video/audio/document/other) — imagery is one kind that
additionally gets variants/presets. This is where the stored-file lifecycle lives;
fastkit-storage stays a thin, DB-free byte contract.

## Installation

```bash
pip install fastkit-files
```

## Models

`StorageFile`, `StorageFileVariant`, `StorageFileReference`, `UploadSession`. A freshly stored asset
is `uploaded`; `process_image` promotes an image to `ready` once its variants exist.
`StorageFileReference` records which record (owner + slot) references an asset.

## Upload and processing flow

```python
session = await file_service.create_upload_session(tenant_id=1, max_size_bytes=5_000_000)
image = await file_service.confirm_image_upload(session.id, data, "photo.png", "image/png")
await file_service.process_image(image.id, AVATAR_PRESET)

# any file (pdf, video, zip, …) — no image validation, kind inferred from content-type
doc = await file_service.confirm_upload(session.id, data, "report.pdf", "application/pdf")
```

`confirm_image_upload` validates size, MIME, real image contents and pixel count;
`confirm_upload` is the generic path for any file (size-capped only). Both store the
object and create an `StorageFile` (status `uploaded`); `process_image` then generates
variants and marks the asset `ready`. On any failure the asset is marked `failed`.

## Attach-on-use lifecycle (no orphans, scalable)

References are explicit and reference-counted through `StorageFileReference`:

```python
await file_service.link_slot("products", product_id, "cover", object_key)   # by URL/object key
await file_service.link("user", user_id, "avatar", asset_id)                # by asset id
await file_service.unlink_owner("products", product_id)                     # on delete
removed = await file_service.cleanup_orphans(older_than_seconds=86400)      # reap unreferenced uploads
```

`link_slot`/`link` reconcile a single (owner, slot): the previous asset is detached
and **purged** (storage object + variants + row) only when no owner still references
it (a shared asset survives). `cleanup_orphans` reaps only assets with **no
attachment** older than the TTL (abandoned uploads the user never saved) via one
indexed query — never a bucket scan, never an in-use file. Run it as a scheduled job.

## Image presets

`ImagePreset` holds `ImageVariantSpec`s with a resize `mode` (`cover`, `contain`,
`fit`, `crop`, `pad`, `max_width`, `max_height`, `original`), target format and
quality. Processing honours EXIF orientation and strips metadata.

## Security

Random object keys, size and pixel limits, decompression-bomb protection, MIME
allow-list, private-by-default storage and orphan cleanup.

## Testing

100% branch coverage, including invalid MIME, oversized, excessive pixels,
processing failure and orphan cleanup.

```bash
pytest packages/fastkit-files --cov=fastkit_files --cov-branch
```
