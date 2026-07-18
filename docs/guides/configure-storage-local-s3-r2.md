# Configure storage (local / S3 / R2)

Storage is a swappable byte backend selected by `settings.storage.provider`. Everything above it
(the [managed-file layer](../packages/files.md), the admin's file fields) is unchanged when you switch.

## Local (default)

```toml
[storage]
provider = "local"
base_url = "/media"
directory = "./data/media"
```

Files are served from `directory` at `base_url`. Good for dev.

## S3

```toml
[storage]
provider = "s3"
base_url = "https://cdn.example.com"
bucket = "my-bucket"
region = "us-east-1"
# credentials via environment or the instance role
```

Writes go through the retry/circuit-breaker so a transient S3 failure degrades gracefully.

## Cloudflare R2 (and other S3-compatible endpoints)

R2, MinIO and friends speak the S3 API — use the `s3` provider with the endpoint set:

```toml
[storage]
provider = "s3"
base_url = "https://media.example.com"
bucket = "my-bucket"
endpoint_url = "https://<accountid>.r2.cloudflarestorage.com"
region = "auto"
```

Set credentials in the environment:

```bash
FASTKIT__STORAGE__PROVIDER=s3
FASTKIT__STORAGE__ACCESS_KEY_ID=…
FASTKIT__STORAGE__SECRET_ACCESS_KEY=…
```

## How things are stored

Every upload becomes a `StorageFile` row (metadata + references) and the bytes are stored under a
random `object_key` (`{tenant}/{shard}/{token}.{ext}`). The `base_url + object_key` is the public URL.
Storage holds only bytes; the DB holds who references them.

## Register a custom provider

Add your own to `storage_providers` — see [Providers](../concepts/providers.md).

> The S3 provider is env-gated and untested in CI (a documented follow-up: it needs a lifecycle to
> enter/close its client). Use local for the default/test path.
