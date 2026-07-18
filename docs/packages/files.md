# fastkit-files

The **managed-file layer**: the `StorageFile` model (a stored file + its metadata + who references
it), generic over any file kind (`StorageFileKind` = file/image/video/audio/document/other — *not*
image-only). This is where the file lifecycle lives, on top of the DB-free [storage](storage.md) byte
contract.

## Upload pipeline

```python
files = context.component("file_service")   # StorageFileService

session = await files.create_upload_session(tenant_id=0)
image = await files.confirm_image_upload(session.id, data, "photo.png", "image/png")  # validated image
doc   = await files.confirm_upload(session.id, data, "report.pdf", "application/pdf") # any file
```

`confirm_image_upload` validates size, MIME, real image contents and pixel count (decompression-bomb
protection); `confirm_upload` is the generic path (size-capped only). Both create a `StorageFile`
(status `uploaded`) and store the bytes.

## Attach-on-use lifecycle (no orphans, scalable)

References are explicit and reference-counted through `StorageFileReference`:

```python
await files.link_slot("products", product_id, "cover", object_key)  # by URL/object key
await files.link("user", user_id, "avatar", file_id)                # by id
await files.unlink_owner("products", product_id)                    # on delete
removed = await files.cleanup_orphans(older_than_seconds=86400)     # reap unreferenced uploads
```

- On save, a referenced file is **attached** (safe from the reaper).
- On replace/clear/delete, the old file is **purged eagerly** (storage object + variants + row) **only
  when no other owner still references it** — a shared file survives until its last owner unlinks.
- `cleanup_orphans` reaps only files with **no reference** older than a TTL (abandoned uploads) — one
  indexed query, never a bucket scan, never an in-use file. Run it as a scheduled job.

The admin wires this automatically for a resource's `file_fields` — see
[Uploads & file fields](../admin/uploads-files.md) and [Handle uploads](../guides/handle-uploads.md).

## Image variants

`ImagePreset` + `process_image` generate variants (thumbnails, formats) with EXIF handling; a bad
image raises `NOT_AN_IMAGE` (422), never a 500.
