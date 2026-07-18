# Theme and branding

The admin uses **Tabler's defaults for everything** — never override its colors, shadows or styles.
Branding is a few explicit knobs.

## Branding

```python
build_page_config(settings.admin, theme={
    "brand_name": "Acme",
    "logo_url": "/media/logo.svg",     # replaces the brand name
    "logo_max_height": 32,
    "favicon": "🚀",                    # emoji or a URL
    "primary_color": "#5b6ee1",        # opt-in; sets Tabler's --tblr-primary
    "forced_locale": None,             # force a single locale
})
```

`primary_color` is opt-in only — the default is stock Tabler.

## Light / dark theme

The navbar has a sun/moon toggle (`data-bs-theme` on `<html>`/`<body>`, persisted in
`localStorage.fk-theme`, applied early in `<head>` to avoid a flash). Everything uses Tabler's theme
variables, so both themes work everywhere. A floating menu stamps the active theme onto itself so it is
self-sufficiently light or dark.

## Custom CSS

`admin.css` holds only a few genuinely-custom component rules (`.fk-upload-preview`, `.fk-lookup-menu`,
the loading affordances, the navigation overlay, the neutral cell/header links) — there is no
primary-color or shadow override. Add your own via `_extra_head.html` if you must, but prefer Tabler
utilities.

## Sidebar

Nav groups are collapsible; the collapsed state **persists across navigations** in `localStorage`, and
the active resource + its group are highlighted. Never use Tailwind. Inherit Tabler markup; do not
hand-roll it.

See [Templates & rendering](templates-rendering.md).
