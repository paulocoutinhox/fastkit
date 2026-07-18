# Error codes

Every `ErrorCode` carries a stable `code`, an HTTP status, a `translation_key`, a severity, and flags
(`should_log`, `user_visible`, `retryable`). The user-facing `text` is the translated
`translation_key` (see [Errors and i18n](../concepts/errors-and-i18n.md)). A boundary test asserts
every `translation_key` has a catalog entry.

## Families

| Prefix | Package | Examples |
|---|---|---|
| `error.*` / `http.*` / `internal.*` | core | `internal.error`, `http.not-found`, `http.method-not-allowed` |
| `validation.*` | core / i18n | every pydantic v2 error type + admin validation (`validation.required`, `validation.string-too-short`, `validation.file-too-large`, …) |
| `authentication.*` | auth | `authentication.invalid_credentials`, `authentication.account_inactive`, `authentication.account_locked`, `authentication.ambiguous_identity`, `authentication.session_invalid` |
| `rate_limit.*` | auth | `rate_limit.login` |
| `captcha.*` | auth | `captcha.required`, `captcha.invalid`, `captcha.expired`, `captcha.provider_unavailable` |
| `file.*` | files | `file.invalid_mime`, `file.too_large`, `file.too_many_pixels`, `file.not_an_image`, `file.upload_session_expired`, `file.processing_failed` |
| `conflict.*` | core | `conflict.unique` |
| `authorization.*` | permissions | `authorization.denied` |

## Codes vs translation keys

- `code` is the machine key surfaced as `message.code` (dotted, e.g. `captcha.invalid`).
- `translation_key` is the catalog key resolved to `text` (kebab-case local, e.g.
  `error.captcha-invalid`).

## `user_visible=False`

For `CACHE_ERROR`, `INTERNAL_ERROR` and similar, the resolver returns only the generic message and
never leaks the internal `exc.message` detail.

## Field errors

`FieldError(field, code, **params)` carries a `validation.*` code and params but no inline message —
the handlers resolve the text from the catalog per locale. Inline-formset field errors additionally
carry a `path = [inline, row_index, field]`.
