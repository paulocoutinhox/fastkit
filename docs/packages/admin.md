# fastkit-admin

The declarative, API-first admin engine: fully server-rendered Jinja (Tabler + jQuery), with a thin
client that enhances the already-rendered DOM. No SPA, no build step.

This package is large — it has its own [Admin section](../admin/resources.md). Start there.

## Map

- [Resources](../admin/resources.md) — `AdminResource[Model]`, the core declaration.
- [Fields](../admin/fields.md) · [Filters](../admin/filters.md) · [Columns](../admin/columns.md) ·
  [Actions](../admin/actions.md)
- [Inlines](../admin/inlines.md) — repeatable child sub-forms.
- [Related-object widget](../admin/related-widget.md) — add/edit/delete a related record in a modal.
- [Dependent selects & lookups](../admin/dependent-selects.md) — cascading options.
- [Uploads & file fields](../admin/uploads-files.md) — the managed-file lifecycle in the admin.
- [Overrides](../admin/overrides.md) — `get_queryset`, `render_<col>`, `sort_<col>`, `resolve`,
  `display_label`.
- [Permissions](../admin/permissions.md) — screen + endpoint guards, audit hook.
- [Templates & rendering](../admin/templates-rendering.md) — override dirs, partials, macros.
- [Client (app.js)](../admin/client-js.md) — the enhancement layer + `FastKit`/`FastKitAdmin`.
- [Dashboard](../admin/dashboard.md) · [Reports in the admin](../admin/reports-in-admin.md) ·
  [Login & captcha](../admin/login-and-captcha.md) · [Theme & branding](../admin/theme.md) ·
  [Translations](../admin/translations.md)

## Wiring

`build_admin_deps(runtime, audit=…)` returns `(deps, security)`; mount the generic routers
(`build_admin_router`, `build_admin_pages_router`, `build_profile_router`, `build_upload_router`) and
`mount_admin_static(app)`. See [Project setup](../getting-started/project-setup.md).
