# FastKit

Modular, extensible and asynchronous ecosystem for FastAPI applications.

FastKit is a monorepo of independently versioned Python distributions that a
consumer project installs selectively. Each package contributes apps, models,
migrations, templates, translations, admin resources, providers and system
checks through public registries and contracts, without the consumer copying
code. Business rules stay in the consumer project — FastKit provides generic,
predictable infrastructure only.

```python
from fastkit_core.app import create_application
from app.settings import get_settings

app = create_application(get_settings())
```

Every package is implemented, documented and tested to **100% branch coverage**,
and the demo admin is verified end-to-end in a real browser with Playwright.

## Documentation

Comprehensive, topic-separated documentation lives in **[`docs/`](docs/README.md)** — getting
started, concepts, data, one file per package, the full admin engine, task-oriented how-to guides,
and reference. [`CLAUDE.md`](CLAUDE.md) is the engineering guide (conventions and invariants).

## Packages

| Package | Topic | Coverage |
| --- | --- | --- |
| [fastkit-core](packages/fastkit-core/DOCS.md) | Runtime, apps, registries, service container, API envelope, errors, events, health/system checks, resilience | 100% (77) |
| [fastkit-config](packages/fastkit-config/DOCS.md) | Typed settings, TOML + env merge, safe public config export | 100% (10) |
| [fastkit-db](packages/fastkit-db/DOCS.md) | Async SQLAlchemy 2, sessions, repository, Unit of Work, dialect capabilities | 100% (24) |
| [fastkit-logging](packages/fastkit-logging/DOCS.md) | Structured logging, SystemLog, AuditLog, sanitization | 100% (15) |
| [fastkit-tenancy](packages/fastkit-tenancy/DOCS.md) | Tenant model, context, resolvers, global tenant semantics | 100% (15) |
| [fastkit-accounts](packages/fastkit-accounts/DOCS.md) | Users, profiles, login identifiers, normalizers | 100% (18) |
| [fastkit-permissions](packages/fastkit-permissions/DOCS.md) | Roles, permissions, authorization, cache | 100% (13) |
| [fastkit-auth](packages/fastkit-auth/DOCS.md) | Sessions, Argon2 passwords, JWT, rate limiting, pluggable captcha (disabled/recaptcha/image), brute-force | 100% (42) |
| [fastkit-cache](packages/fastkit-cache/DOCS.md) | Cache contract, file/database providers | 100% (19) |
| [fastkit-storage](packages/fastkit-storage/DOCS.md) | Storage contract, local and resilient S3 providers, signed URLs | 100% (18) |
| [fastkit-tasks](packages/fastkit-tasks/DOCS.md) | Persistent task queue and scheduler, workers, leases, retry | 100% (33) |
| [fastkit-files](packages/fastkit-files/DOCS.md) | Managed files (any kind), variants, uploads, image processing, security | 100% (27) |
| [fastkit-mail](packages/fastkit-mail/DOCS.md) | Async email, templates, resilient providers, deliveries | 100% (19) |
| [fastkit-i18n](packages/fastkit-i18n/DOCS.md) | Modular gettext-style translations, locale resolution | 100% (12) |
| [fastkit-content](packages/fastkit-content/DOCS.md) | Languages, per-language content (key + html/plain), HTML sanitizer | 100% (33) |
| [fastkit-admin](packages/fastkit-admin/DOCS.md) | Declarative, API-first admin engine; every field type, relation/lookup/dependent selects, fieldset cards, sortable/clickable grid | 100% (122) |
| fastkit-vendor-* | Vendored front-end libs (jQuery, Tabler, Tabler Icons, TinyMCE, JSONEditor) served from packages, never a CDN | n/a |
| [fastkit-reports](packages/fastkit-reports/DOCS.md) | Report definitions and renderers (screen, PDF, CSV) | 100% (13) |
| [fastkit-webhooks](packages/fastkit-webhooks/DOCS.md) | Webhook inbox, signature verification, idempotency | 100% (11) |
| [fastkit-cli](packages/fastkit-cli/DOCS.md) | Aggregated command line interface | 100% (13) |
| [fastkit-testkit](packages/fastkit-testkit/DOCS.md) | Factories, fakes and fixtures for testing | 100% (12) |

## Admin frontend

The admin is **server-rendered** by `fastkit-admin`: Jinja templates styled with
**Tabler (Bootstrap) + jQuery** served from vendored `fastkit-vendor-*` packages (never a CDN),
driven by a jQuery client that consumes the general JSON **`/api`**. There is no build step and no SPA framework. It uses
Tabler's real vertical layout (collapsing sidebar, mobile hamburger, Bootstrap
dropdowns), a solid design (no shadows), and translates every string (dynamic through
`FastKit.t`, server-rendered through `data-i18n`); English and Portuguese ship. Grids
support Django-style overrides (`get_queryset`, `render_<column>`, `sort_<column>`,
`pk_field`) and `read_only` resources.

Templates are fragmented into partials and macros and customized the Django way — a
project overrides any page or fills an empty extension partial
(`admin/_extra_head.html`, `_extra_js.html`, `_pre_footer.html`, `_sidebar_footer.html`,
`_navbar_end.html`, …) by dropping a same-named file in its own templates directory,
without copying the base. The client renders every field type as a Tabler widget
(a TinyMCE rich text editor with image upload, relation and cascading dependent
selects, autocomplete lookups that open on focus, color picker, image/file uploads
with preview and lightbox, per-language content editing, and url/email/masked fields
with validation), groups forms into full-width fieldset cards, and gives the grid
sortable and clickable columns, view/edit/delete row actions, bulk actions (with a
select-all when the resource has them), an id column, primary-key default ordering,
and Django-style dash cells for empty values. **Every destructive action
shows a confirmation dialog** (including deleting a record's stored files). A public
UI layer, `window.FastKit` (`toast`/`confirm`/`modal`/`alert`/`lightbox`/`api`/
`upload`), lets a project build its own UI without touching Tabler, and
`window.FastKitAdmin` lets external jQuery add cell renderers (that may return live
interactive elements), row actions, listen to events and refresh a row or the grid.
The interface language follows the browser (English fallback); the login captcha is
pluggable (disabled/recaptcha/image, or a consumer provider); theme (brand, logo, colors,
favicon) comes from `window.__FASTKIT__`.

Continuous integration ([.github/workflows/ci.yml](.github/workflows/ci.yml)) runs
the coverage gate and the Playwright suite, with a Postgres service
([docker-compose.yml](docker-compose.yml)) for integration and connection-failure
tests.

## Demo

The [demo application](examples/demo) wires every package together with SQLite,
local storage, local image processing, a local mail provider, JWT sessions and
Argon2 passwords, following GDPR/LGPD principles (self-service data export and
erasure). It defines its own menu groups, resources, `Category`/`Subcategory`
tables driving relation and dependent selects, and a `Showcase` entity that
exercises every admin field type in grouped fieldsets, manages role permissions
grouped by permission group, and supports multi-source login per tenant (email,
phone, CPF, CNPJ, username, social) unique per tenant. It also records an activity
log (create/update/delete, login, logout, profile changes) shown through a read-only
admin resource. The home page is a single plain-CSS page with a centered "FastKit"
title; the admin is the server-rendered Tabler UI at `/admin`.

```bash
make install          # virtualenv + every workspace package
make install-admin    # Playwright e2e dependencies
make seed             # seed the demo database
make dev              # run the demo API on :8100
make coverage         # Python suite with a 100% branch coverage gate
make test-e2e         # Playwright browser suite (login, CRUD, permissions, ...)
```

## Principles

- Selective installation, independent updates, migrations and templates per package.
- API-first, asynchronous, single response envelope, normalized errors.
- Configured provider only — no automatic provider fallback.
- Tenant isolation, backend-authoritative permissions, no mutable global singletons.
- No side effects on import; deterministic bootstrap ordering.
- Every public success and error path is tested; 100% branch coverage per package.
