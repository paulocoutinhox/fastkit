# Errors and i18n

## Error codes

An `ErrorCode` (`fastkit_core.errors.codes`) is a stable, typed value:

```python
ErrorCode("form.invalid", 422, "error.form-invalid", Severity.warning, should_log=False)
#          code             http  translation_key      severity        logging
```

- `code` — a stable machine key (`context.local`), surfaced as `message.code`.
- `translation_key` — the catalog key resolved to the user-facing `text`.
- `http_status`, `severity`, `should_log`, `user_visible`, `retryable`.

Raise them as exceptions:

```python
from fastkit_core.errors.exceptions import ValidationError, FieldError

raise ValidationError(VALIDATION_FAILED, message="…dev detail…",
                      field_errors=[FieldError("email", "validation.invalid-email")])
```

A **boundary test** asserts every `ErrorCode.translation_key` across all packages has a
`BASE_CATALOGS["en"]` entry — a code can never ship without its translation.

## The Translator

`fastkit-i18n` is the single translation authority. `Translator` merges catalogs and resolves a
locale's full catalog via `messages(locale)`. Keys are **`context.local`, kebab-case local part**:
`error.invalid-email`, `grid.apply`, `validation.string-too-short`, `login.failed`. Never camelCase,
never a deeper path.

```python
translator.gettext("validation.string-too-short", locale="pt", limit=3)
```

`Translator.gettext` formats leniently (`format_map` with a lenient dict, catching
`ValueError`/`IndexError`), so a catalog string with a wrong or literal-brace placeholder degrades to
the raw template instead of raising inside the exception handler.

## Catalogs

- **Framework error + validation strings** live in `fastkit_i18n.catalogs.BASE_CATALOGS` — en + pt,
  the two complete built-in locales, including every `error.*` and `validation.*` string across all
  packages (auth, files, mail, storage…).
- **Admin UI chrome** lives in `fastkit_admin.messages.ADMIN_MESSAGES`, registered by `AdminApp`.
- **Resource-declared strings** (labels/titles) are gettext-style: the English string is its own key
  and falls back to itself, translated server-side by `resource.translate_schema`.

## Pydantic coverage is total

`PYDANTIC_CODE_MAP` maps **every** `pydantic_core` `ErrorType` (all 104) to a `validation.*` catalog
key. A boundary test asserts the map covers the full `ErrorType` set (a pydantic upgrade that adds a
type fails the suite) and that every mapped key plus the generic fallback exists in `BASE_CATALOGS`
en+pt. So no validation error ever surfaces a raw code.

## Extending

Add keys or a whole new locale from your app's `register_translations`:

```python
def register_translations(self, context):
    context.component("translator").add_catalog("es", {"login.submit": "Entrar", ...})
```

`LocaleResolver` consults `translator.supported()` live, so a registered locale is immediately
resolvable from `Accept-Language`/cookie. The client copy is pushed per request (`FastKit.t`). See
[Add a locale / translations](../guides/add-locale.md).
