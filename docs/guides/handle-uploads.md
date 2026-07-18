# Handle uploads (image / file / avatar)

Uploads go through the [managed-file layer](../packages/files.md), so referenced files are attached and
abandoned ones are reaped.

## 1. Upload handlers

A handler takes bytes and returns `{"url": …, "file_id": …}`. Route through the file service:

```python
def build_image_upload_handler(runtime, base_url):
    files = runtime.component("file_service")
    async def handler(data, filename, content_type):
        session = await files.create_upload_session(tenant_id=0)
        stored = await files.confirm_image_upload(session.id, data, filename, content_type)
        return {"url": f"{base_url}/{stored.object_key}", "file_id": stored.id}
    return handler

def build_file_upload_handler(runtime, base_url):
    files = runtime.component("file_service")
    async def handler(data, filename, content_type):
        session = await files.create_upload_session(tenant_id=0)
        stored = await files.confirm_upload(session.id, data, filename, content_type)
        return {"url": f"{base_url}/{stored.object_key}", "file_id": stored.id}
    return handler
```

## 2. Mount the upload router

```python
context.routers.include(
    build_upload_router(deps, {"image": image_handler, "file": file_handler}),
    prefix=api_path, source=self.name,
)
```

`POST /api/uploads/{kind}` is size-capped (default 25 MiB → 422). An image is validated
(dimensions, decompression-bomb protection); a bad image is a clean 422, never a 500.

## 3. Reference the file from a resource

```python
class ProductAdmin(AdminResource[Product]):
    form_fields = [ImageField("image_url", upload_url="/api/uploads/image")]
    file_fields = ["image_url"]
    def render_image_url(self, row, locale):
        return cover_thumb(row.image_url)
```

Wire `instance.assets = context.component("file_service")` and `instance.media_base_url =
settings.storage.base_url`. The admin then attaches on save, purges on replace/clear, and unlinks on
delete — automatically. See [Uploads & file fields](../admin/uploads-files.md).

## 4. Reap orphans at scale

Schedule `file_service.cleanup_orphans()` as a nightly task (see
[Scheduled tasks](scheduled-tasks-worker.md)).
