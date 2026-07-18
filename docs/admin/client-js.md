# Admin client (app.js)

A **thin jQuery enhancement layer** built on the public `FastKit` library. It does **not** route or
render screens — the server does. On DOM-ready it reads `window.__FASTKIT__`, restores a flash toast
(so a "Created"/"Updated" survives the post-save full-page navigation), fires `fastkit:ready`, and runs
per-screen `init*` functions that detect their screen by DOM markers.

## What `enhance(root)` boots

From the server-rendered `data-*`: masks, color, uploads, TinyMCE richtext, JSONEditor,
relation/lookup selects (options + `depends_on` cascades, value-first on edit), the permission matrix
and translations. `collect($form)` reads every `.fk-field[data-type]` into a payload (including nested
inline rows) and submits to `/api`; errors go through `FastKit.formErrors`.

## The grid does jQuery AJAX

Search / sort / paginate / filter and row-delete / bulk swap the server's `?_fragment=table` HTML into
`#grid` — never a full reload. Datetime/number cells are formatted client-side in the user's
timezone/locale. Navigation is a **full page load**, so there is no client render-race; a
[loading overlay](templates-rendering.md) covers the destination while the next page loads.

## The public UI library — `window.FastKit`

The interface every consumer talks to, so nobody depends on Tabler/Bootstrap directly:

- `FastKit.toast(kind, msg)`, `FastKit.confirm(opts)`, `FastKit.modal(opts)`, `FastKit.alert(msg)`,
  `FastKit.lightbox(src)`
- `FastKit.api(method, path, body)`, `FastKit.upload(url, file)`
- `FastKit.t(key)`, `FastKit.registerMessages(locale, dict)`
- **`FastKit.formErrors($scope, err, {aliases})`** — the single way to surface API errors on a form
  (never hand-roll a `.catch`).
- `FastKit.captcha.register(name, {mount})` — register a login captcha client adapter (see
  [Login & captcha](login-and-captcha.md)).

Build all new UI through these — internally they speak to Tabler/jQuery.

## The extensibility bridge — `window.FastKitAdmin`

External scripts (loaded via `_extra_js.html`) can:

- `registerCellRenderer` (may return an HTML string or a live jQuery/DOM element for interactive cells),
- `registerHeaderRenderer`, `registerRowAction`,
- listen to `fastkit:*` events (`cell-click`, `action`, `ready`),
- call `refreshGrid()` / `refreshRow(id)` to refresh keeping filters and page.

The demo's `showcase.js` (loaded via a template override) shows badges, computed cells, a click-to-edit
ajax modal that patches one row, a boolean toggle, and refreshing row actions. See
[Extend the admin client](../guides/extend-admin-client.md).
