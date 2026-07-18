# fastkit-content

Languages, content, and per-language translations (pyaa-style: a stable key + html/plain body per
language).

## Model

- **`Language`** — code, name, native name, active/default, sort order.
- **`Content`** — a stable `key`, tenant-scoped.
- **`ContentTranslation`** — the body (html + plain) for a `(content, language)` pair.

## Service

```python
content = context.component("content_service")
await content.set_translation(content_id, language_id, html="…", plain="…")
value = await content.by_key("home.hero", language="pt")
```

`set_translation`/`publish` raise `NotFound` for a missing content id (never a 500). A duplicate
translation is idempotent (insert-first, catch `IntegrityError`, re-fetch).

## Router

Mount `build_content_router(runtime, security, publish_permission="content.publish", tenant_id=0)` —
the `publish_permission` and `tenant_id` are parameters with defaults. The admin edits content per
language with a `TranslationsField` (see [Fields](../admin/fields.md)).

## Content by key

Read published content filtered by language at your content-by-key endpoint
(`/api/content-by-key/{key}?language=…` in the demo).
