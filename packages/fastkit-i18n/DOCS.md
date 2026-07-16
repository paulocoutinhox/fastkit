# fastkit-i18n

Interface translations and locale resolution for FastKit.

## Installation

```bash
pip install fastkit-i18n
```

## Locale resolution

`LocaleResolver` resolves the active locale in order: user preference, tenant
preference, cookie, `Accept-Language`, then the default. Only supported locales
are ever selected.

The active locale lives in a `ContextVar` (`get_locale`, `set_locale`), never a
mutable global.

## Fallback chain

`fallback_chain("pt-BR", ["pt_BR", "pt", "en"], "en")` yields
`["pt_BR", "pt", "en"]`. Variants resolve to their base and finally the default.

## Translator

Keys follow `context.local` with a kebab-case local part (e.g. `error.not-found`,
`validation.integer-invalid`, `grid.apply`).

```python
translator.gettext("error.not-found", locale="pt")       # "O recurso solicitado não foi encontrado."
translator.ngettext("one", "many", count, locale="en")
with translator.activate("pt"):
    ...
```

Translations are modular. Any app or the host project can register new keys for an
existing locale, or add a brand new locale, through `add_catalog`. Because the
`LocaleResolver` reads `translator.supported()` live, the new locale resolves from
`Accept-Language` immediately:

```python
translator.add_catalog("de", {"error.not-found": "Nicht gefunden."})  # new locale, now supported
translator.supported()                                                # ["de", "en", "pt"]
translator.messages("pt_BR")                                          # full catalog for a frontend
```

`messages(locale)` returns the whole catalog for a locale resolved through its
fallback chain, which is what a frontend consumes to translate its own keys. The
admin client mirrors this with `FastKit.registerMessages(locale, dict)`.

`install_i18n(env, translator)` exposes `_`, `gettext` and `ngettext` in Jinja.
The package seeds the framework's English and Portuguese base catalogs (every
`error.*` and `validation.*` string); a project adds locales or keys with `add_catalog`.

## Testing

100% branch coverage.

```bash
pytest packages/fastkit-i18n --cov=fastkit_i18n --cov-branch
```
