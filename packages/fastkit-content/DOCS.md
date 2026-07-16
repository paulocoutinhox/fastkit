# fastkit-content

Languages, translatable content and secure HTML sanitization for FastKit.

## Installation

```bash
pip install fastkit-content
```

## Models

- `Language` — code, base code, native name, direction, active/default/system,
  sort order. Exactly one default is enforced.
- `Content` — keyed per tenant (`unique(tenant_id, key)`), typed, with a status.
- `ContentTranslation` — one row per `(content, language)` with title, summary,
  body and version.

## Languages

`LanguageService.seed_defaults` idempotently inserts English, Portuguese and
Spanish. `set_default` guarantees a single default language.

## Content

```python
node = await content_service.ensure_content("home.hero", tenant_id=1)
await content_service.set_translation(node.id, language.id, body="<p>Welcome</p>")
value = await content_service.get("home.hero", "pt_BR", tenant_id=1, supported=["en", "pt"])
await content_service.publish(node.id)
```

`get` resolves through the locale fallback chain and skips locales without a
Language row. Rich-text and HTML content is sanitized on write.

## HTML sanitization

Content bodies are cleaned with `fastkit_core.sanitize.sanitize_html` (the shared
framework sanitizer, also the default for the admin `RichTextField`). It allow-lists
tags, attributes and URL schemes, removes `<script>`/`<style>` and their contents,
strips `on*` handlers, blocks `javascript:` and non-image `data:` URLs, drops unknown
tags while keeping their text, and escapes text nodes.

## Testing

100% branch coverage, including XSS/injection penetration cases.

```bash
pytest packages/fastkit-content --cov=fastkit_content --cov-branch
```
