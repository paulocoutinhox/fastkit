# Response envelope

Every API response is a single, stable shape (`fastkit_core.api.envelope`):

```json
{
  "success": true,
  "message": { "code": "form.created", "text": "Created." },
  "data": {},
  "errors": [],
  "meta": { "request_id": "…" }
}
```

- `success` — boolean.
- `message` — `{code, text}` or `null`. A stable `code` plus a **translated** `text`.
- `data` — the payload.
- `errors` — a list of field errors on validation failures.
- `meta` — request metadata (e.g. `request_id`, pagination).

```python
from fastkit_core.api.envelope import success_envelope, build_message

return success_envelope(data={"id": "1"}, message=build_message("form.created", "Created."))
```

## Error text is resolved in one place

A single resolver — `errors.handlers.resolve_error_text` — owns the user-facing text, and **all**
exception handlers funnel through it. The text is the **runtime-translated `code.translation_key`**
(a proper, localized sentence), falling back to `exc.message` only when no translator is available,
else a translated generic fallback. So `text` is **never null** and never a lowercase inline dev
string when i18n is present.

`exc.message` is therefore **developer detail** (the exception's `str()`, logs) — a user-facing
custom message is a **catalog entry** under its own code, not an inline string. For a code with
`user_visible=False` (`CACHE_ERROR`, `INTERNAL_ERROR`) the resolver returns only the generic message,
never leaking internal detail.

## Field errors are consistent and centrally displayed

Validation `FieldError`s carry a `code` (`validation.*`) + `params` but **no inline message** — the
exception handlers resolve the text from the catalog (`translator.gettext(code, locale, **params)`).
Pydantic and admin validation are both translated this way. Inline-formset errors are per-row: each
`FieldError` is tagged with `path = [inline_name, row_index, field_name]`, and the client routes it to
the exact row.

## Every HTTP error is enveloped too

A `StarletteHTTPException` handler maps `exc.status_code` to an `ErrorCode` (`HTTP_STATUS_CODE_MAP`:
4xx → an `http.*` code, 5xx → `internal.error`), builds the standard envelope through
`resolve_error_text`, keeps the original status and preserves `exc.headers` (e.g. `Allow`,
`WWW-Authenticate`). A custom user-facing message must be raised as a `FastKitError` (which carries
`message`/`field_errors`), not a raw `HTTPException`.

See [Errors and i18n](errors-and-i18n.md) and the [Response envelope shape](../reference/envelope-shape.md).
