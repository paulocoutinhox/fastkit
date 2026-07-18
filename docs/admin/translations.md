# Admin translations

Translations are **backend-concentrated and pushed to the client** (Django-style — one authority, the
JS holds a copy).

## The flow

The `Translator` (fastkit-i18n) is the single source. The pages router injects
`translator.messages(locale)` + the resolved `locale` into `window.__FASTKIT__` per request, and
`FastKit.t(key)` reads that copy (`CONFIG.messages[key] || key`) — the client ships **no** embedded
catalog. Server-rendered strings use `data-i18n="key"` filled by `FastKit.localize()`.

The active locale is resolved **on the backend** (`config.forced_locale` else `Accept-Language`/cookie
via `LocaleResolver`, falling back region → base `pt-BR` → `pt`).

## Keys

`context.local`, **kebab-case local part**: `error.invalid-email`, `grid.apply`,
`validation.string-too-short`, `login.failed`. Never camelCase, never a deeper path.

## What lives where

- **Framework error/validation** → `fastkit_i18n.catalogs.BASE_CATALOGS` (en + pt).
- **Admin UI chrome** → `fastkit_admin.messages.ADMIN_MESSAGES`.
- **Resource-declared strings** (resource/column/filter/fieldset/field titles) → gettext-style: the
  English string is its own key and falls back to itself, translated server-side by
  `resource.translate_schema` (which takes a `translate`) and, for the sidebar, by `render_shell`.
  Column headers are Title-Cased from the field name while field labels keep their declared case, so
  register both forms.

## Wiring resource translations

```python
def register_translations(self, context):
    context.component("translator").add_catalog("pt", {"Products": "Produtos", "Name": "Nome"})
```

Wire `AdminDeps(translate=…)` (auto-wired by `build_admin_deps`). Add keys or a whole new locale from
your `register_translations`; `FastKit.registerMessages(locale, dict)` is the supplementary client hook.

See [Errors and i18n](../concepts/errors-and-i18n.md) and
[Add a locale / translations](../guides/add-locale.md).
