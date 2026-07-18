# fastkit-storage

A deliberately thin, **DB-free byte contract** — `put` / `get` / `delete` / `exists` — with local and
resilient S3 providers.

```python
storage = context.component("storage")
await storage.put("2/ab/xyz.png", data, content_type="image/png")
data = await storage.get("2/ab/xyz.png")
```

## Providers

Selected by `settings.storage.provider`:

- **`local`** — filesystem. Derives content type from the object key (`mimetypes`), never a
  module-global dict.
- **`s3`** — resilient (wraps writes in the retry/breaker). Works with S3-compatible endpoints
  (AWS S3, Cloudflare R2, MinIO…) via its endpoint/credentials settings.

See [Configure storage (local/S3/R2)](../guides/configure-storage-local-s3-r2.md).

## Storage is NOT the file registry

Storage is just bytes at a key. It has **no database** and knows nothing about who references a file.
The **managed-file layer** (a stored file + metadata + references + the upload/cleanup lifecycle)
lives one layer up in [fastkit-files](files.md) — never a second parallel file registry in storage.

## Known follow-up

The S3 provider is env-gated and untested in CI; it needs a lifecycle to enter/close its aioboto3
client and its own `bucket` setting. Documented, to be implemented fully when needed.
