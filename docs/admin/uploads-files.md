# Uploads and file fields

A resource's image/file fields are backed by the [managed-file layer](../packages/files.md), with an
**attach-on-use lifecycle** so referenced files are never reaped and abandoned uploads are cleaned at
scale.

## Declaring a file field

```python
IMAGE_UPLOAD_URL = "/api/uploads/image"

class ProductAdmin(AdminResource[Product]):
    list_columns = [Column("image_url", label="Cover", sortable=False), "name", ...]
    form_fields = [ImageField("image_url", label="Cover", upload_url=IMAGE_UPLOAD_URL), ...]
    file_fields = ["image_url"]        # the columns whose lifecycle the admin manages

    def render_image_url(self, row, locale):
        return cover_thumb(row.image_url)   # an <img> thumbnail for the grid/detail
```

Wire the collaborator in `register_admin`:

```python
instance.assets = context.component("file_service")
instance.media_base_url = context.settings.storage.base_url
```

## What happens

1. The `ImageField` renders the upload widget. Picking a file **POSTs immediately** to
   `upload_url` → the file is stored and a `StorageFile` (status `uploaded`) is created → the object URL
   is returned and written into the hidden input.
2. On **create/update**, the resource calls `assets.link_slot(resource_name, record_id, field,
   object_key)` for each file field — attaching the file (reference-counted, safe from the reaper) and,
   when a value is replaced/cleared, detaching + eagerly purging the old file **only if no other owner
   references it**.
3. On **delete**, `assets.unlink_owner(resource_name, record_id)` detaches all the record's files.

Uploads are size-capped (`read_upload`, default 25 MiB → 422 `validation.file-too-large`), and every
upload goes through the file service (there is no raw `storage.put` bypassing the registry).

## The upload endpoints

`POST /api/uploads/{kind}` — keyed by kind (`image`, `file`, …). Each handler returns
`{"url": …, "file_id": …}`. The profile avatar uses a dedicated handler that crops to a centered
square (`process_variant`, 512×512, webp).

## Cleanup at scale

`cleanup_orphans` reaps only `StorageFile`s with **no reference** older than a TTL — wire it as a
scheduled task (the demo's nightly `demo.cleanup`). It never touches an in-use avatar/cover.

See [Handle uploads](../guides/handle-uploads.md) and
[Configure storage (local/S3/R2)](../guides/configure-storage-local-s3-r2.md).
