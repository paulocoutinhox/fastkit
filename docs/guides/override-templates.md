# Override admin templates

The `AdminRenderer` searches your override directories **before** the package templates, so you
customize a screen the Django way — drop a same-named file in your own `templates/` dir.

## 1. Point the renderer at your dir

`build_admin_pages_router` uses an `AdminRenderer`; construct it with your override dir:

```python
from fastkit_admin.rendering import AdminRenderer
renderer = AdminRenderer(override_dirs=["myproject/templates"])
```

## 2. Override a piece

Copy only the fragment you want to change. To replace the login card:

```
myproject/templates/admin/partials/login_card.html
```

The renderer picks your file over the package's. Because templates are fragmented (`base.html` →
`head.html`/`scripts.html`, `app.html` → `sidebar.html`/`navbar.html`/`content`), you override a small
piece without copying the whole shell.

## 3. Inject without copying (fill-in partials)

Prefer the empty fill-in partials for additions — no copying at all. Create any of these in your
override dir:

| Partial | Injects into |
|---|---|
| `_extra_head.html` | `<head>` |
| `_extra_js.html` | before `</body>` (load your client scripts here) |
| `_pre_body.html` / `_pre_footer.html` / `_post_footer.html` | page regions |
| `_sidebar_footer.html` | bottom of the sidebar |
| `_navbar_end.html` | end of the navbar |

## Rules

- **Use Tabler's defaults** — don't override its colors/shadows/styles. For branding use `theme=` (see
  [Theme & branding](../admin/theme.md)).
- Inherit the package macros (`brand`, `nav_menu`, `asset_link`, `asset_script`) so a package change
  doesn't break your override.

See [Templates & rendering](../admin/templates-rendering.md).
