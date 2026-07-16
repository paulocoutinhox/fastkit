# fastkit-assets

Assets, image variants and secure uploads for FastKit, backed by fastkit-storage.

## Installation

```bash
pip install fastkit-assets
```

## Models

`Asset`, `AssetVariant`, `AssetAttachment`, `UploadSession`. An asset is only
usable when its status is `ready`.

## Upload and processing flow

```python
session = await asset_service.create_upload_session(tenant_id=1, max_size_bytes=5_000_000)
asset = await asset_service.confirm_image_upload(session.id, data, "photo.png", "image/png")
await asset_service.process_image(asset.id, AVATAR_PRESET)
```

Confirmation validates size, MIME, real image contents and pixel count, stores
the original, then processing generates variants and marks the asset `ready`. On
any failure the asset is marked `failed`.

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
pytest packages/fastkit-assets --cov=fastkit_assets --cov-branch
```
