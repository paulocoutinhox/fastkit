# fastkit-storage

Object storage for FastKit with one contract and local + S3 providers. Only the
configured provider per alias is used — there is no fallback.

## Installation

```bash
pip install fastkit-storage
pip install "fastkit-storage[s3]"
```

## Providers

- `LocalStorageProvider` — filesystem storage with atomic writes and HMAC-signed,
  expiring local URLs. Object keys are validated against traversal (`safe_key`).
- `S3StorageProvider` — S3-compatible storage over an injected aioboto3-style
  async client, with real presigned upload/download URLs. Mutating operations
  retry transient failures with exponential backoff behind a `CircuitBreaker`.

Providers are pluggable by name: `storage_providers.register("gcs", factory)`
(`fastkit_storage.providers`) adds a backend a project selects via
`settings.storage.provider` — no framework edit needed.

## Operations

`put`, `get`, `delete`, `exists`, `stat`, `copy`, `move`, `presign_upload`,
`presign_download`, `health`. Objects are private by default; access is granted
through short-lived signed URLs.

```python
stat = await storage.put("avatars/1.webp", data, content_type="image/webp")
url = await storage.presign_download("avatars/1.webp", expires_in=300)
```

## Testing

100% branch coverage, including path-traversal rejection, signature expiry and
provider health failure.

```bash
pytest packages/fastkit-storage --cov=fastkit_storage --cov-branch
```
