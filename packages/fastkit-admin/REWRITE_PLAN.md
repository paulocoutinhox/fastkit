# Admin frontend rewrite — server-rendered, componentized, jQuery (MEGA-LIST)

Living checklist for the full admin frontend rewrite. Goal: move screen rendering from the
1373-line client `admin.js` into **server-rendered Jinja templates**, one overridable partial per
piece (Django-admin style), with **writes going to `/api`**, **jQuery** (kept — NO new lib, NO
htmx) for behavior + grid AJAX, and **inlines** (repeatable/nested sub-forms). When 100% done +
tested + documented, fold the architecture into CLAUDE.md and delete this file.

Hard rules (standing): no legacy / no back-compat / no gambiarra / no "it used to be X" checks;
English only; rare comments; no sentence-splitting semicolons; only do what genuinely makes sense;
100% branch coverage + e2e green; document everything in CLAUDE.md. **Keep jQuery — do not add
any new front-end library.**

## Locked decisions
- Reads: **Jinja server-render** from the existing `resource.py` methods (`list`, `get_object`,
  `grid_schema`, `form_schema`). Writes: **`/api`** via jQuery (keeps API-first).
- Grid dynamism (search/sort/paginate/row-refresh): **jQuery AJAX partial swap** — the server
  returns the `partials/_table.html` fragment (detected via a `?_fragment=table` query flag or an
  `X-Requested-With` header) and jQuery replaces `#grid`. No full-page reload, no new lib.
- Every piece is an overridable template resolved through the existing `AdminRenderer` ChoiceLoader
  (consumer drops the same-named file). Field/column/filter widgets become partials keyed by type.
- Nested data: `AdminResource.inlines` (repeatable child sub-forms). The form serializes
  `{...main, <inline>: [ {...child}, ... ]}` and submits to the resource write endpoint; the
  consumer can own the transaction for interdependent data.

## Phase 0 — Foundation
- [x] No new library. jQuery stays (already vendored). Nothing to vendor.

## Phase 1 — Rendering infrastructure (`fastkit_admin/screens.py` new module)
- [ ] Server-side screen builders that call resource methods and return template context:
  `list_context`, `form_context`, `detail_context`, `report_context`, `profile_context`.
- [ ] Path dispatch in `build_admin_pages_router`: `{path}/{resource}` → list; `.../new` → create
  form; `.../{id}` → detail; `.../{id}/edit` → edit form; `.../reports/{name}` → report;
  `.../profile` → profile; root → dashboard. Anonymous → redirect login (keep).
- [ ] Grid fragment: the list route returns only `partials/_table.html` when `?_fragment=table`
  (or `X-Requested-With: fetch`) is present, so jQuery can swap `#grid` on search/sort/paginate.
- [ ] Server-side **permission gating** on every screen route (reuse `check_permission`/`authorize`).
- [ ] Field partial dispatch: `partials/fields/<field_type>.html`, a `field()` macro that picks the
  partial by `field.type` and passes `field`, `value`, `errors`, `locale`.
- [ ] Column/cell/header + filter partial dispatch (same pattern).

## Phase 2 — List screen (`list.html` + partials)
- [ ] `list.html`: toolbar card (search when `search_fields`, right btn-list: Filters toggle,
  bulk/collection actions, New), filter panel (grouped by `filter_fieldsets`), grid card
  (`table-responsive` > datatable), footer (showing + numeric pagination).
- [ ] `partials/_table.html` (thead + tbody), `partials/_row.html` (one row), `partials/_cell.html`
  (type-aware: boolean icon, date/number in user tz/locale — keep client formatting via a small
  enhancer OR server-format; decide), `partials/_pagination.html`.
- [ ] Sortable headers: htmx links carrying current query (`?sort=-x&...`), single chevron icon.
- [ ] Row actions dropdown (view/edit/custom/delete) — links + delete confirm (JS). Bulk actions
  dropdown + collection action buttons. Selection column only when bulk ops exist.
- [ ] Filters: each filter → `partials/filters/<type>.html`; Apply/Clear via htmx GET; Enter submits.
- [ ] Empty state, `html` columns (author `render_<column>`) rendered safe; row VALUES escaped.

## Phase 3 — Form screen (`form.html` + field partials)
- [ ] `form.html`: fieldsets as cards, each field via the `field()` macro; drop empty fieldsets on
  create; full-width single column (current layout decision).
- [ ] A partial for EVERY field type: text, textarea, email, url, masked, password, number, decimal,
  boolean (switch), date, time, datetime, select, multiselect, relation, lookup, color, json,
  richtext, image, file, permission_matrix, translations. `hide_label`, `help_text`, `readonly`,
  `required` honored. Wide types span full width.
- [ ] Virtual fields (permission_matrix, translations) render their edit UI (matrix = subheader +
  divider + responsive grid, NO nested cards — already the client design).
- [ ] Submit: JS collects the form (+ inlines) and does `POST`/`PATCH` `/api/resources/{r}` →
  success toast + navigate; validation errors filled into `[data-error]` via `FastKit.formErrors`
  (reuse). Save/Cancel.
- [ ] `[data-error]` slot next to every field for centralized error display.

## Phase 4 — Inlines (nested sub-forms) — NEW capability
- [ ] `AdminResource.inlines: list[InlineResource]` — child resource, fk field, min/max, label.
- [ ] `partials/inline.html`: a repeatable sub-form block (child fields via the same `field()`
  macro) + Add/Remove controls. Template overridable.
- [ ] JS helper `initInlines`: add/remove a row (clone a `<template>` prototype), renumber, respect
  min/max. Serialize to a nested payload `{ <inline_name>: [ {...}, ... ] }`.
- [ ] Write path: submit the whole graph to the resource endpoint; document how a consumer owns the
  transaction (interdependent main + children). Support at least one level of nesting; design the
  serializer recursively so nested inlines are possible.
- [ ] Read/edit: server-render existing children as inline rows with values.

## Phase 5 — Detail screen (`detail.html`)
- [ ] Read-only render of every field via `partials/detail/<type>.html` (or a `detail_field()`
  macro): image lightbox, file link, richtext `.html` (sanitized), json `<pre>`, boolean icon,
  color swatch, `—` for empty, `_html[name]` for author render overrides.
- [ ] permission_matrix read-only (granted, grouped — already designed). Inlines listed read-only.
- [ ] Edit/Close buttons (edit only when `can_update`).

## Phase 6 — Report / Profile / Dashboard
- [ ] `report.html`: filter panel (same filter partials) + table + export links (CSV/HTML/PDF);
  Run via htmx; Enter applies; export links carry flattened params.
- [ ] `profile.html`: server-rendered sub-forms (avatar upload, display/first/last, password, login
  identifiers with type select). Each submits to the profile router/API; field errors centralized.
  Live header identity update + avatar persist stay.
- [ ] `dashboard.html`: server-rendered shell + `FastKitAdmin.registerDashboard` hook stays (JS).

## Phase 7 — Thin JS enhancement layer (rewrite `admin.js`)
- [ ] Strip ALL `render*`/`build*` screen renderers. Keep only enhancers: confirm/modal/toast
  (`FastKit`), lookup autocomplete (AJAX to options), TinyMCE init, JSONEditor init, input masks,
  dependent-select cascades, inline add/remove, theme toggle, sidebar drawer close, **grid AJAX**
  (jQuery `$.get` the `?_fragment=table` partial on search/sort/paginate → swap `#grid`, with a
  stale-response guard + `.catch` toast), form submit → `/api` + `FastKit.formErrors`.
- [ ] `FastKitAdmin` extension bridge: re-target to server-rendered DOM (registerCellRenderer via a
  hook that re-runs after each grid AJAX swap; registerRowAction; events; refreshGrid re-fetches
  the fragment).
- [ ] Delete dead helpers; keep `window.FastKit` public API.

## Phase 8 — i18n / permissions / security / robustness
- [ ] Templates translate chrome + resource-declared strings server-side (`deps.translate`); the
  client catalog stays only for JS-side messages.
- [ ] Jinja autoescape ON; only author `render_<column>` output marked `| safe`; row values escaped;
  `window.__FASTKIT__` still escaped.
- [ ] Every screen + fragment route permission-gated; NotFound/empty handled (no 500 on bad path/id).
- [ ] Keep existing "never 500 on bad input" guards that still apply.

## Phase 9 — Review lens (standing ask, do throughout)
- [ ] Hunt bugs / races / legacy / dead code while rewriting; remove the old client renderers fully;
  no gambiarra, no back-compat shims. Note anything found + fix or document.

## Phase 10 — Tests
- [ ] Python 100% branch coverage for `screens.py` + new pages router dispatch + any new resource
  code (inlines). Extract module-level handlers, unit-test via direct `await`; httpx for routes.
- [ ] Rewrite/adjust the 63 Playwright specs for server-rendered + htmx flows; ADD specs for inline
  add/remove + nested submit. Every field type + screen still covered.

## Phase 11 — Docs
- [ ] Rewrite the CLAUDE.md "Admin frontend" section entirely (server-rendered, partial-per-piece,
  override model, htmx, inlines, thin JS, writes→API). Update the memory build-status file.
- [ ] Delete this REWRITE_PLAN.md once folded in.

## Migration strategy (avoid a half-migrated live admin)
The old `admin.js` still owns routing + renders every screen into `#content`. Do NOT wire the new
server-rendered screens into the live router one at a time (they'd fight the client render). Instead:
build the new templates + `screens.py` + the thin `admin.js` **in parallel**, unit-test partials in
isolation (render a partial via `AdminRenderer.render` with a fixture context), and **flip
everything together at the end**: pages-router screen dispatch goes live in the SAME change that
swaps the old `admin.js` for the thin enhancement layer. No back-compat window.

## Grounded data shapes (from resource.py)
- `list(session, query, locale)` → `{rows: [serialize_row...], pagination: OffsetPage.to_meta()}`.
- `serialize_row` → `{id, <col>: value|html}` (html when a `render_<col>` exists → mark cell safe).
- `grid_schema(flags, translate)` → `{resource, label, columns[], filters[], filter_fieldsets[],
  actions[], search_fields, default_sort, page_size, page_size_options, select_all, permissions,
  flags}`; each column: `{name, label, align, sortable, clickable, type→field_type, html}`.
- `permission_flags(check)` → `{can_list, can_detail, can_create, can_update, can_delete}`.
- `form_schema(mode, translate)` → `{fieldsets: [{title, description, fields: [field.to_schema()...]}], actions}`.
- `serialize_detail` → `{id, _display, <field>: value, _html: {<field>: html}}`.
- Shell: `base.html` has `{% block content %}`; `app.html` fills it (sidebar+navbar+`#content`).
  **Restructure:** app.html must expose `{% block screen %}` inside `#content` so screen templates
  `{% extends "admin/app.html" %}` + override it (Jinja blocks don't cross `{% include %}`, so the
  `#content` div + block move into app.html; `partials/content.html` folds in).

## Open decisions to settle while building
- Cell formatting (date/number/tz) server-side vs a tiny client enhancer — lean: server-format with
  the user tz/locale (we have it), drop the client formatter.
- Grid fragment detection: `?_fragment=table` query flag vs `X-Requested-With` header — lean: query
  flag (works with plain jQuery `$.get`, no custom header wiring).
