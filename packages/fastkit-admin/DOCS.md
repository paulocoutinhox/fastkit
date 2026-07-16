# fastkit-admin

Declarative, API-first admin engine for FastKit. Everything is extensible: a
consumer project defines its own resources, menus, fields, filters and actions
and shapes the admin without forking FastKit.

## Installation

```bash
pip install fastkit-admin
```

## Resources

```python
class ProductAdmin(AdminResource[Product]):
    name = "products"
    model = Product
    list_columns = ["name", Column("price", align="right"), "is_active", "badge"]
    search_fields = ["name"]
    filters = [TextFilter("name"), EnumFilter("status", choices=STATUS), DateRangeFilter("created_at")]
    actions = [AdminAction(name="deactivate", label="Deactivate", scope="bulk", confirm=True)]
    form_fields = [TextField("name", required=True), DecimalField("price")]
    permissions = {"list": "products.view", "create": "products.create", "update": "products.update", "delete": "products.delete"}

    def render_badge(self, row, locale):
        return f'<span class="badge">{row.category}</span>'

    async def action_deactivate(self, session, rows, locale):
        for row in rows:
            row.is_active = False
        await session.commit()
        return {"deactivated": len(rows)}
```

Any column can be overridden with a `render_<column>` method returning custom
HTML, and `Column` sets alignment (`left`/`center`/`right`) and sortability.

## Fields

`TextField`, `TextareaField`, `EmailField`, `URLField`, `MaskedField`,
`PasswordField`, `NumberField`, `DecimalField`, `BooleanField`, `DateField`,
`TimeField`, `DateTimeField`, `SelectField`, `MultiSelectField`, `RelationField`,
`LookupField`, `ColorField`, `JsonField`, `RichTextField` (sanitized on write, with
an image `upload_url`), `ImageField`, `FileField`, `PermissionMatrixField`,
`TranslationsField`. Email, URL and masked (with a validation `pattern`) fields
validate on the backend; decimals, dates and times are formatted and parsed per
locale. `hide_label=True` drops a field's label (use the fieldset title); a
`Fieldset(title, [names], description=…)` shows the description as a hint under the
title. A resource that lists `file_fields` and is given a `storage` + `media_base_url`
removes those stored objects when a record is deleted.

Fields marked `virtual=True` (such as `PermissionMatrixField`) are not persisted as
model columns. They render in the form and save through their own endpoints. The
`PermissionMatrixField` renders permissions grouped by permission group as
checkboxes and reads and writes the selection through the given URLs.

## Relation and dependent selects

`RelationField` renders a select whose options are records of another table. The
owning resource provides the options through an `options_<field>` handler, which
builds each option label however it wants:

```python
class ProductAdmin(AdminResource[Product]):
    form_fields = [
        RelationField("category_id", label="Category"),
        RelationField("subcategory_id", label="Subcategory", depends_on=["category_id"]),
    ]

    async def options_category_id(self, session, parent_values, locale):
        rows = (await session.execute(select(Category))).scalars().all()
        return [{"value": row.id, "label": row.name} for row in rows]

    async def options_subcategory_id(self, session, parent_values, locale):
        category_id = parent_values.get("category_id")
        if not category_id:
            return []
        rows = (await session.execute(select(Subcategory).where(Subcategory.category_id == int(category_id)))).scalars().all()
        return [{"value": row.id, "label": row.name} for row in rows]
```

Options are served by `GET /resources/{resource}/options/{field}`; parent values
arrive as query parameters. When `depends_on` is set the field is a dependent
select: it stays empty until its parents have a value, and it resets (cascading to
its own dependents) whenever a parent changes or is cleared. Chains can be any
number of levels deep.

`LookupField` is the autocomplete variant: the handler additionally receives the
typed query under `q` and, when preloading the current value, the id under `value`.
It supports `depends_on` too, so lookups can influence each other.

## Grid

Columns declare `sortable` and `clickable`. Clicking a sortable header sorts by that
column; override how a column sorts with a `sort_<column>()` method returning a
SQLAlchemy expression. Override the base query with `get_queryset()` (filter, join,
restrict columns) and a cell's HTML with `render_<column>(row, locale)`. `pk_field`
(default `"id"`) sets the column used as the record id in payloads, the row checkbox
and lookups, so a model with a non-`id` primary key works. A clickable cell opens the
record — the edit screen when the user may edit, otherwise the read-only detail
screen. `select_all = False` hides the header select-all checkbox.
`GET /resources/{r}/{id}/row` returns a single serialized grid row so a client can
refresh one row without reloading the grid.

`read_only = True` makes a resource view-only — `permission_flags` reports
`can_create/update/delete = False` and those methods raise. Single and bulk delete
both call `delete()` per record, so `file_fields` cleanup and DB cascades always run.

`AdminDeps.audit(action, resource_type, resource_id)`, when provided, is invoked after
create/update/delete for an audit trail.

The Vue admin exposes `window.FastKitAdmin` so external scripts can register cell and
header renderers, add row actions, listen to `fastkit:*` events, and call
`refreshGrid()` / `refreshRow(id)`.

## Fieldsets

`fieldsets` groups the form into titled sections, stacked one under another. Every
field spans the full width. Without `fieldsets` the form renders as a single group.

```python
class ProductAdmin(AdminResource[Product]):
    fieldsets = [
        Fieldset("Details", ["name", "sku", "price"], description="Basic information."),
        Fieldset("Classification", ["category_id", "subcategory_id"]),
    ]
```

## Filters

`TextFilter`, `ExactFilter`, `BooleanFilter`, `NumberFilter`, `ChoiceFilter`,
`EnumFilter`, `MultiChoiceFilter`, `DateFilter`, `TimeFilter`, `DateTimeFilter`,
`DateRangeFilter`. Only registered fields ever reach SQL.

## Actions

Row and bulk `AdminAction`s run through `POST /resources/{r}/{id}/actions/{a}` and
`POST /resources/{r}/actions/{a}`. Handlers are `action_<name>` methods.

## Navigation and view-only

`AdminSite` holds consumer-defined menu groups and items. `navigation(check)`
returns only the items the user may see and drops empty groups. The schema
endpoint returns per-action `flags` (`can_create`, `can_update`, `can_delete`, …)
so the UI renders a read-only view when the user can only list.

## Profile and uploads

`build_profile_router` gives the signed-in user self-service over their profile,
password, login identifiers (email, phone, CPF, CNPJ, username, social) and
avatar. `build_upload_router` powers image/file fields and the rich text editor
through an injected, storage-agnostic upload handler.

## Server-rendered UI (Tabler)

The admin ships a server-rendered UI, not a SPA. `AdminRenderer` (`rendering.py`) is
a Jinja environment whose `ChoiceLoader` searches consumer template directories
before the package templates, so a project overrides any page or fills an empty
extension partial (`admin/_extra_head.html`, `_extra_js.html`, `_pre_body.html`,
`_pre_footer.html`, `_post_footer.html`) the Django way.

`build_page_config(admin_settings, theme=…, recaptcha=…)` produces the template
context and the `window.__FASTKIT__` bootstrap (api base, admin path, brand, forced
locale, reCAPTCHA). `build_admin_pages_router(renderer, site, deps, config)` serves
`{path}/login` and the authenticated shell, redirecting anonymous users to login.
`STATIC_DIR` holds `admin.js` (a jQuery client that renders login, grid, form, detail
and profile from `/api`, with a confirmation dialog before every destructive action)
and `admin.css`; mount it at `/admin-static`. `AdminDeps.get_optional_user` resolves
the current user without raising so the shell can redirect anonymous visitors.

Templates are fragmented into `partials/` (head, scripts, sidebar, navbar, content,
login card) plus macros (`macros.html`) and empty fill-in partials (`_extra_head`,
`_extra_js`, `_pre_body`, `_pre_footer`, `_post_footer`, `_sidebar_footer`,
`_navbar_end`) so a project overrides only what it needs.

The shell uses Tabler's vertical layout (collapsing sidebar, mobile hamburger,
Bootstrap dropdowns from Tabler's JS) and a solid design (shadows disabled through
Tabler CSS variables). Every string is translated — dynamic through `FastKit.t`,
server-rendered through `data-i18n` attributes filled by `FastKit.localize()`.

`static/fastkit-ui.js` exposes `window.FastKit` — the public interface layer
(`toast`, `confirm`, `modal`, `alert`, `lightbox`, `api`, `upload`, `t`, `localize`)
that speaks to Tabler/jQuery internally, so consumers never depend on the framework.
External scripts extend the grid through `window.FastKitAdmin` (cell/header renderers
that may return live elements, row actions, `fastkit:*` events,
`refreshGrid`/`refreshRow`). Uploads are `POST /uploads/{kind}`. Password fields use
`autocomplete="new-password"`.

## Testing

100% branch coverage, including localized fields, every filter, custom actions,
permission-aware navigation, view-only flags, the profile/upload routers, template
rendering with consumer overrides and the server-rendered pages. Browser behaviour is
covered end-to-end by the Playwright suite in `frontend/admin`.

```bash
pytest packages/fastkit-admin --cov=fastkit_admin --cov-branch
```
