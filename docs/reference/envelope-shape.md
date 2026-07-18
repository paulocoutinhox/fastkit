# Response envelope shape

Every API response (`fastkit_core.api.envelope`) has this shape. See
[Response envelope](../concepts/response-envelope.md) for the semantics.

## Success

```json
{
  "success": true,
  "message": { "code": "form.created", "text": "Created." },
  "data": { "id": "42", "name": "Widget" },
  "errors": [],
  "meta": { "request_id": "1a2b3c" }
}
```

`message` may be `null` (no user-facing message). `data` is the payload. For a list, `meta` carries
pagination:

```json
"meta": { "request_id": "…", "page": 1, "page_size": 25, "total_items": 132, "total_pages": 6 }
```

## Error

```json
{
  "success": false,
  "message": { "code": "validation.failed", "text": "Some fields are invalid." },
  "data": null,
  "errors": [
    { "field": "email", "code": "validation.invalid-email", "text": "Enter a valid email.",
      "path": ["email"] }
  ],
  "meta": { "request_id": "1a2b3c" }
}
```

- `message.code` — the stable error code (dotted).
- `errors[].field` — the form field name (e.g. `value` for identifier normalizers).
- `errors[].code` — the `validation.*` catalog key.
- `errors[].text` — the translated message.
- `errors[].path` — `[field]` for a plain field, or `[inline_name, row_index, field_name]` for an inline
  row.

## Builders

```python
from fastkit_core.api.envelope import success_envelope, build_message

success_envelope(data={...}, message=build_message("form.updated", "Updated."))
```

Errors are produced by the exception handlers from raised `FastKitError`/`ValidationError` — you rarely
build an error envelope by hand.
