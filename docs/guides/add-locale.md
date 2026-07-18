# Add a locale or translations

## Add keys to an existing locale

From your app's `register_translations`:

```python
def register_translations(self, context):
    translator = context.component("translator")
    translator.add_catalog("pt", {
        "Products": "Produtos",      # resource label (gettext-style, English key)
        "Name": "Nome",              # column header (Title-cased)
        "name": "Nome",              # field label (declared case)
    })
```

Column headers are Title-Cased from the field name while field labels keep their declared case, so
register both forms.

## Add a whole new locale

Just add a catalog under the new locale code:

```python
translator.add_catalog("es", {
    "login.submit": "Entrar",
    "grid.apply": "Aplicar",
    # …the keys you use
})
```

`LocaleResolver` consults `translator.supported()` live, so `es` is immediately resolvable from
`Accept-Language`/cookie (with region → base fallback, `es-MX` → `es`). The two built-in complete
locales are **en** and **pt**; any other locale is a consumer catalog.

## Keys

Always `context.local`, kebab-case local part: `error.invalid-email`, `grid.apply`,
`validation.string-too-short`. Never camelCase, never a deeper path.

## Client

The active locale's full catalog is pushed to the browser per request; `FastKit.t(key)` reads it.
`FastKit.registerMessages(locale, dict)` is the supplementary client hook (merges into the active
catalog). See [Admin translations](../admin/translations.md) and
[Errors and i18n](../concepts/errors-and-i18n.md).
