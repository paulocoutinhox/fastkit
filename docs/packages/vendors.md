# Vendor packages

FastKit ships one **zero-dependency package per vendored front-end library**, so nothing loads from a
CDN and you bump a library by bumping its own package.

| Package | Library |
|---|---|
| `fastkit-vendor-jquery` | jQuery |
| `fastkit-vendor-tabler` | Tabler (Bootstrap) CSS/JS |
| `fastkit-vendor-tabler-icons` | Tabler Icons |
| `fastkit-vendor-tinymce` | TinyMCE 7 (self-hosted, GPL key, no cloud) |
| `fastkit-vendor-jsoneditor` | JSONEditor |

## How they work

Each package ships its files under `static/` and registers them through the **`fastkit.assets`**
entry point group. It declares a `MOUNT`, a `STATIC_DIR`, and an ordered `ASSETS` list (each with
`kind` css/js, a `path`, an `order`, and optional per-tag `attrs` such as TinyMCE's `referrerpolicy`).

At runtime, `AssetRegistry.discover()` (fastkit-admin) collects every installed provider, orders the
tags, and `mount_assets(app)` serves each package's files. The `asset_link`/`asset_script` template
macros render the tags in `<head>`/before `</body>`.

> Note: this front-end "asset" system (`fastkit.assets` entry point, `AssetRegistry`) is distinct
> from the user-uploaded [managed-file layer](files.md) (`StorageFile`, `fastkit-files`). "Asset"
> here means a static vendored front-end library.

## Bumping a library

Change the version inside the relevant `fastkit-vendor-*` package — templates never name a URL.

## reCAPTCHA

reCAPTCHA is the one intentionally-remote script (it must load from Google), and only when the active
captcha provider is `recaptcha`. See [Login & captcha](../admin/login-and-captcha.md).
