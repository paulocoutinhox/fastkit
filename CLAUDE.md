# CLAUDE.md — FastKit engineering guide

This file is the single source of truth for any AI or engineer working on FastKit.
Read it before writing code. It describes what exists, where it lives, why it is
there, and the exact standards every change must follow.

## What FastKit is

FastKit is a modular, asynchronous ecosystem for FastAPI applications, shipped as a
monorepo of independently versioned Python distributions. A consumer project
installs only the packages it needs and contributes apps, models, admin resources,
providers and system checks through public registries and contracts. Business rules
live in the consumer project; FastKit provides generic, predictable infrastructure.

Everything is async. Every package is documented and tested to **100% branch
coverage**. The admin frontend is verified end-to-end in a real browser.

## Repository layout

```
packages/fastkit-*        one installable distribution each (src layout)
  fastkit-admin/…/templates admin Jinja templates (Tabler shell, override partials)
  fastkit-admin/…/static     app.js (thin jQuery enhancement layer) + admin.css
examples/demo             reference app wiring every package together
frontend/admin            Playwright e2e harness (no framework; runs the demo)
tests/                    cross-package boundary tests
Makefile                  install / test / coverage / e2e / lint
docker-compose.yml        postgres + redis for local integration testing
.github/workflows/ci.yml  coverage gate + Playwright suite
```

Each package is `packages/fastkit-X/src/fastkit_X/` plus `DOCS.md`, `pyproject.toml`
(with a `[project.entry-points."fastkit.apps"]` entry) and `tests/`.

### Packages and their purpose

- **fastkit-core** — runtime, apps, registries, service container, request context,
  API envelope, error codes/handlers (with i18n message resolution), events, health
  and system checks, and `resilience` (circuit breaker, retry with backoff).
- **fastkit-config** — typed settings from TOML + env, safe public config export.
- **fastkit-db** — async SQLAlchemy 2 engine (`pool_pre_ping` + `pool_recycle`),
  session factory, repository, unit of work, dialect capabilities, base + mixins.
- **fastkit-logging** — structured logging, `SystemLog`, `AuditLog`, sanitization.
- **fastkit-tenancy** — `Tenant` model (name, image_url, code…), tenant context,
  resolvers, global-tenant semantics (`tenant_id = 0` ⇄ persisted `NULL`).
- **fastkit-accounts** — users, profiles, login identifiers and normalizers.
- **fastkit-permissions** — permissions, roles (a role *is* the permission set — no
  separate group), authorization with a versioned cache.
- **fastkit-auth** — sessions, Argon2 passwords, JWT, rate limiting, reCAPTCHA v3.
- **fastkit-cache** — cache contract, file/database/Redis providers (Redis degrades
  behind the shared circuit breaker).
- **fastkit-storage** — storage contract, local and resilient S3 providers.
- **fastkit-tasks** — persistent task queue and scheduler with durable retry. The
  queue/scheduler only persist and materialize work; a **`Worker` must run to execute it**.
  `Worker.run_once()` leases + runs one execution; `Worker.drain(scheduler)` = one cycle
  (`scheduler.tick()` → `queue.reclaim_expired()` → run every ready execution); `Worker.run(
  poll_interval, scheduler)` is the long-running loop (drain, sleep, repeat until cancelled — a
  cancel is never swallowed since `CancelledError` is a `BaseException`, and it always sleeps to
  yield). `TasksApp` registers `task_registry`, `task_queue` and `task_scheduler` components. **Any
  running server is also a worker**: `TasksApp.startup/shutdown` spawn/cancel an in-process
  `Worker.run()` when `settings.tasks.run_worker` is true — no demo glue, a first-class setting
  (`worker_id`, `worker_queues`, `worker_lease_seconds`, `poll_interval_seconds`). Set it with
  `FASTKIT__TASKS__RUN_WORKER=true` (`make dev` and `make worker` both do; tasks/e2e leave it unset
  so they stay deterministic) — `make worker` just boots the runtime as a standalone worker process.
  Task **handlers must be registered** (`registry.task(name, queue=…)`) or the worker fails the
  execution `retryable=False` — the demo registers them in `app/tasks.py`.
- **fastkit-assets** — assets, variants, uploads, image processing.
- **fastkit-mail** — async email, templates, resilient providers, deliveries.
- **fastkit-i18n** — the single translation authority (`Translator` merges catalogs, resolves a
  locale's full catalog via `messages(locale)`), locale resolution, and `catalogs.BASE_CATALOGS`
  (every framework `error.*` + `validation.*` string). Keys are `context.local`, kebab-case local.
- **fastkit-content** — languages, content and per-language translations (pyaa-style
  key + html/plain body).
- **fastkit-admin** — declarative, API-first admin engine.
- **fastkit-vendor-\*** — one zero-dependency package per vendored front-end library
  (`fastkit-vendor-jquery`, `-tabler`, `-tabler-icons`, `-tinymce`, `-jsoneditor`). Each
  ships the library files under `static/` and registers them through the `fastkit.assets`
  entry point. Nothing loads from a CDN — bump a library version in its own package.
- **fastkit-reports**, **fastkit-webhooks**, **fastkit-cli**, **fastkit-testkit**.

## Architecture

- An **app** is a `FastKitApp` subclass (`fastkit_core.apps.base`) declaring `name`,
  `requires`, and lifecycle hooks (`register_services`, `register_models`,
  `register_admin`, `register_routers`, …). Apps are discovered through the
  `fastkit.apps` entry point group.
- The **Runtime** bootstraps apps in dependency order, builds registries (models,
  routers, templates), a component/service container and health/system checks.
- `create_application(settings)` builds the FastAPI app, installs the request
  context middleware and the three exception handlers, and mounts routers. It sets
  `app.state.fastkit` to the runtime.
- **Response envelope** (`fastkit_core.api.envelope`): every response is
  `{success, message: {code, text} | null, data, errors, meta}`. Errors carry a
  stable `code` and a translated `text`. **A single resolver — `errors.handlers.resolve_error_text`
  — owns the message text** (all exception handlers funnel through it): user-facing text is the
  **runtime-translated `code.translation_key`** (a proper, localized sentence), falling back to
  `exc.message` only when no translator is available, else a translated generic fallback — so `text`
  is **never null** and is never a lowercase inline dev string when i18n is present. `exc.message` is
  therefore **developer detail** (the exception's `str()`, logs), not the user-facing copy: a custom
  user message is a **catalog entry** under its own code, not an inline string. For a code with
  `user_visible=False` (`CACHE_ERROR`, `INTERNAL_ERROR`) it returns only the generic message,
  **never leaking the internal detail**.
- **Validation errors cover 100% of pydantic v2.** `PYDANTIC_CODE_MAP` maps **every** `pydantic_core`
  `ErrorType` (all 104) to a `validation.*` catalog key — a boundary test asserts the map covers the
  full `ErrorType` set (a pydantic upgrade that adds a type fails the suite) and that every mapped key
  plus the generic fallback exists in `BASE_CATALOGS` en+pt, so no validation error ever surfaces a
  raw code. `GENERIC_VALIDATION_CODE` is only the defensive default for a future/unknown type, not a
  routine outcome.
- **Every non-validation HTTP error is enveloped and translated too.** A `StarletteHTTPException`
  handler (404 unknown route, 405 wrong method, and any raw `HTTPException` a dependency or middleware
  raises) maps `exc.status_code` to an `ErrorCode` via `HTTP_STATUS_CODE_MAP` (4xx → an `http.*` code,
  5xx → `internal.error`), builds the standard envelope through `resolve_error_text`, keeps the
  original status and **preserves `exc.headers`** (e.g. `Allow`, `WWW-Authenticate`). A custom
  user-facing message must be raised as a `FastKitError` (which carries `message`/`field_errors`), not
  a raw `HTTPException` — the four handlers are registered together in `FastKit.install`.
- **Field errors are consistent, translated and centrally displayed.** Server side, validation
  `FieldError`s use the **form field name** as `field` (e.g. every `fastkit_accounts` identifier
  normalizer raises under `field="value"`, not the identifier type) and carry a `code` + `params`
  **but no inline message** — the exception handlers resolve the text from the catalog
  (`localize_field_errors` → `translator.gettext(code, locale, **params)`), so pydantic and admin
  validation are both translated (see the Translations section). Client side, **one helper
  `FastKit.formErrors($scope, err, {aliases})`** fills every `[data-error]` slot, focuses/scrolls
  the first errored field, and toasts only when no field matched — every form (resource
  create/edit, all profile sub-forms, add-identifier) goes through it, never a bespoke `.catch`.
- **The admin never 500s on ordinary bad input.** Field parsers that coerce (`NumberField`,
  `RelationField`/`LookupField` `int()`, `MultiSelectField` list) raise a 422 `FieldError`, not a
  raw `ValueError`/`TypeError`. `DateField`/`TimeField`/`DateTimeField` reject a non-string JSON value
  (list/dict/number) with a 422 `FieldError` instead of an `AttributeError` from `strip()`, and
  `DecimalField` rejects `bool`/list/dict (a numeric JSON value is still accepted) instead of an
  `InvalidOperation`/`AttributeError`; `SelectField`/`MultiSelectField.validate` guard the choice
  membership test with an `isinstance(str)` check so an unhashable value (`{"status": []}`,
  `{"tags": [["x"]]}`) raises a 422, not a `TypeError`. Grid filters coerce the query-string value to the column's Python
  type via a shared `filters._coerce_for_column` (used by one `EqualityFilter` base) and **skip
  the filter** if it does not parse — so `filter[price]=abc` can't raise a Postgres `DataError`.
  `DateRangeFilter.apply` returns the query unchanged when the value is not a `{from,to}` dict (a
  flat `filter[created_at]=abc` can't raise `AttributeError`). `get_object` **coerces the id to
  `int` only when the PK column is `Integer`** (a non-numeric id against an integer PK returns
  `NotFound`, and a numeric id against a String PK stays a string — no `varchar = integer` Postgres
  `DataError`), and `bulk_action` ignores a non-list `ids`. A genuinely **out-of-range** integer
  (a 40-digit id/filter/page) is deliberately **left to error at the driver** (a clean, non-leaking
  `internal.error` 500) — bound-checking every int against its column range is not worth the code;
  absurd numeric input is not "ordinary bad input".
- **Resilience** (`fastkit_core.resilience`): `CircuitBreaker`, `RetryPolicy`
  (exponential backoff + jitter) and `run_with_retry(op, policy, breaker=…)`. Used by
  the Redis cache provider, the mail service and the S3 storage provider. External IO
  must degrade gracefully, log the failure and recover on its own.
- **Concurrency & correctness invariants** (do not regress):
  - **Service container** (`services/container.py`): singleton creation is guarded by a
    per-key `asyncio.Lock` (double-checked) so a service is built exactly once under
    concurrency; circular-dependency detection uses a per-resolution-chain `ContextVar`
    (never a container-global set) so two independent concurrent resolutions can't raise a
    bogus "circular dependency".
  - **Permissions are tenant-scoped**: `_role_ids_for_user` filters `UserRole` by
    `tenant_id == persisted OR tenant_id IS NULL` (global) — a role assigned in one tenant
    must never grant permissions in another. The permission cache's `set(..., observed_version)`
    refuses to write if `bump_version()` ran during the compute await (no stale re-cache).
    `Authorizer.has_permission` checks `is_active` **before** the `is_root` short-circuit, so a
    deactivated root is not authorized.
  - **Authentication is tenant-scoped**: `AccountService.find_candidates(requested_tenant_id, …)`
    matches a `LoginIdentifier` only when `tenant_id == persisted OR tenant_id IS NULL` (global) —
    the same email/phone/cpf registered in tenant A never authenticates a login into tenant B, and
    a global identifier (root/staff) authenticates anywhere. `LoginIdentifier` uniqueness is the
    functional index over `coalesce(tenant_id, 0), type, normalized_value`, so the same value can
    exist independently per tenant.
  - **The acting user's tenant is stamped into the request context**: `AdminSecurity.get_current_user`
    calls `update_request_context(user_id=…, tenant_id=user.tenant_id)`, so `SystemLog`/`AuditLog`
    (which read `context.tenant_id`) record the actor's tenant, not `None`.
  - **EventBus.emit** iterates a snapshot (`handlers_for`), never the live handler list.
  - **Task worker** resolves the task in its own try — an unregistered task fails
    `retryable=False` (no infinite crash loop), while a handler's own `KeyError` still retries.
    The success path runs `complete()` + `_record_attempt()` **outside** the handler `try`, so a
    bookkeeping failure after a task genuinely succeeded can never re-drive `fail()` and flip a
    succeeded execution to failed (it stays leased and re-runs — at-least-once).
  - **Task finalization is lease-guarded**: `complete`/`fail`/`_finalize` take the `worker_id` and
    write via a conditional `UPDATE … WHERE id=? AND locked_by=? AND status='running'` (rowcount
    checked), so a worker whose lease already expired and was reclaimed can never clobber the state
    of the worker that now legitimately holds it (it becomes a no-op). Mirrors `heartbeat`/`lease`.
  - **Webhook `process()` claims with a CAS** — a conditional `UPDATE … WHERE status IN
    (received, retrying)` (rowcount==1) before running the handler, so two concurrent
    `process(event_id)` calls can't both run the side effect or double-count `attempt_count`.
  - **Login failure counting is atomic** — `_register_failures` does `UPDATE … SET
    failed_login_count = failed_login_count + 1` (not a read-modify-write), then sets `locked_until`
    with a conditional `UPDATE … WHERE failed_login_count >= max`, so parallel wrong-password
    guesses can't under-count and slip past the lockout.
  - **Scoped services are lock-guarded too** — `ServiceScope.get` for a `scoped` lifetime uses the
    same double-checked per-key `asyncio.Lock` as the singleton path, so two concurrent resolutions
    of one scoped key in a shared scope yield a single instance.
  - **Scheduler** advances a slot (`_advance`) **only** on `IntegrityError` (a peer already
    materialized it); any other enqueue error logs and does not advance, so a transient DB blip
    re-selects the still-due task next `tick()` instead of silently dropping the run.
  - **Idempotent writes under a unique constraint** insert-first then catch `IntegrityError`
    and re-fetch (webhooks `_store_valid` **and** `_store_rejected` — a replayed bad-signature
    payload can't 500; accounts `create_user`/`add_identifier` map a duplicate-in-payload or
    concurrent insert to `ConflictError`, not a raw 500); asset variant saves delete-then-insert so
    reprocessing is idempotent. `set_role_permissions` de-dups its `permission_ids` and maps an
    `IntegrityError` (unknown role/permission) to a 422 `FieldError`; `grant_permission`/`assign_role`
    catch a duplicate `IntegrityError` and no-op (idempotent, never a 500).
  - **Malformed client input never 500s the framework**: `Accept-Language` with a bad `q=`
    value is skipped (`i18n/locale.parse_accept_language`); a valid-signed webhook whose body is
    not JSON (or lacks `id`) is stored **rejected**, not raised; plus the admin bad-input rules above.
  - **Health checks are isolated**: `HealthCheckRegistry.run` catches each check and reports it
    `unavailable` with the error detail — a raising probe degrades the report, never 500s `/health`.
  - **A 500 envelope carries the real request id**: the context middleware stamps
    `request.state.request_id`, and the catch-all handler reads it (the request context is already
    reset by the time `ServerErrorMiddleware` runs, so `meta.request_id` would otherwise be a fresh
    random). `ModelRegistry.register` retains each model's `source` and names it in the
    duplicate-registration error.
  - **Login hardening**: the rate-limit bucket is keyed on the **normalized** identifier
    (`account.normalize_identifier`), so casing/whitespace variants of one account share a bucket;
    the login runs a throwaway `PasswordHashService.dummy_verify` whenever **no** real argon2 verify
    ran — an unknown identifier *or* a known passwordless/social-only account whose `password_hash` is
    `NULL` — so timing matches a password account and neither is a user-enumeration oracle; a
    successful login **transparently rehashes** the stored password (`needs_rehash` → policy-free
    `rehash`, persisted in place) when the argon2 parameters changed; an unknown `identifier_type` returns
    `INVALID_CREDENTIALS` (not a `KeyError` 500, not an enumeration signal); passwords are capped at
    `auth.password_max_length` (argon2 never hashes an unbounded payload).
  - **More "never 500 the admin" guards**: `AdminSite.navigation` tolerates a menu item pointing at
    an unregistered resource (returns no permission, doesn't `KeyError` the whole shell);
    `run_action` raises `NotFound` when a declared action has no `action_<name>` method;
    `AccountService.update_profile`/`set_password_hash` raise `NotFound` for a missing user;
    `images.process_variant` raises `FastKitError` (not a bare `KeyError`) for an unknown output
    format. **A translation lookup never crashes**: `Translator.gettext` formats leniently
    (`format_map` with a lenient dict, catching `ValueError`/`IndexError`), so a catalog string with
    a wrong or literal-brace placeholder degrades to the raw template instead of raising inside the
    exception handler.
  - **Provider health checks resolve the live component**: cache/storage `_health` reads
    `context.component("…")` at check time, so a consumer that overrides the provider via
    `set_component` gets a health check for its provider, not the discarded framework one.
  - **More request-path 500 guards**: `parse_grid_query` forces a dict for a range part, so a mixed
    `filter[x]=a&filter[x][from]=b` can't raise `TypeError`; admin `create`/`update` catch a
    unique-constraint `IntegrityError` and raise a 409 `ConflictError` (not a 500); content
    `set_translation`/`publish` raise `NotFound` for a missing content id; a webhook whose
    valid-signed body is JSON but **not an object** (`[]`, `123`) is stored *rejected*, not raised.
  - **Uploads are size-capped**: `helpers.read_upload(file, max_bytes)` (default
    `DEFAULT_MAX_UPLOAD_BYTES` = 25 MiB) reads with a hard cap and raises a 422
    `validation.file-too-large` — the upload and profile-avatar routers take a `max_bytes` param so
    a huge body can't exhaust memory.
  - **A registered task's retry policy is authoritative**: `TaskQueue` holds the `task_registry` and
    `enqueue` fills `max_attempts`/`timeout`/`retry_delay` from the `TaskDefinition` when the caller
    does not override them, so a declared `registry.task(name, max_attempts=5, timeout=300, …)` policy
    applies to both scheduled and manually-enqueued executions (an explicit `enqueue` argument still
    wins; an unregistered name falls back to `1`/`60`/`5`).
  - **Task scheduling is robust**: `cron` supports `*`, ranges (`9-17`), steps (`*/2`, `1-9/2`),
    lists and POSIX **`7` as Sunday** (normalized to `0`), raising `CronError` (never a bare
    `ValueError`) for a bad token; day-of-month and
    day-of-week use POSIX **OR** semantics when both are restricted; an invalid `cron_expression`
    **disables** that schedule (`_compute_next` catches `CronError`) instead of stalling `tick()`
    forever. `TaskQueue.reclaim_expired` moves a lease-expired task already at `attempt_count >=
    max_attempts` to `failed` (a one-shot task whose worker died is not silently re-run).
  - **Report CSV export neutralizes formula injection** (`_csv_safe` prefixes a cell starting with
    `= + - @` tab/CR with `'`); `HtmlRenderer` escapes. **Log sanitization** redacts a broader
    marker set (`api_key`/`bearer`/`cvv`/`ssn`/…) and, past the depth cap, redacts a whole
    container rather than passing a deep secret through. **Subdomain tenant resolution** requires a
    real `.base_domain` boundary (so `notexample.com` is not a subdomain of `example.com`).
  - **UnitOfWork always clears its after-commit hooks** (`finally`), so a raising hook can't leave
    stale callbacks on a reused unit.
  - **Config + logs are robust**: an env override that descends into a scalar
    (`FASTKIT__A__B` where `A.B` is a value) overwrites the node so it surfaces a Pydantic
    `ValidationError`, never a bare `TypeError` from walking into a `str`. `logging.sanitize`
    redacts secret keys by specific markers (`api_key`/`bearer`/`cvv`/`ssn`/`card_number`/…) — never
    an over-broad `card` that would hide `wildcard` — and redacts whole containers past its depth
    cap so a deep-nested secret can't leak. `SystemLogService.record` resolves the log level by name
    (`logging.getLevelName`), so a lowercase level (`warning`) logs at the correct level instead of
    raising `TypeError` from `getattr(logging, "warning")` returning a function.
  - Local storage derives content type from the object key (`mimetypes`), never a module-global
    dict (which was lost on restart and grew unbounded).
  - **Client stale-write / failed-request guards** (app.js): navigation is a **full page load** (the
    server renders each screen), so there is no SPA render-race to token-guard — a response can never
    write into a screen the user already left. What remains are the in-screen async guards: the
    lookup widget's search carries a per-widget sequence id (`seq`; stale responses ignored) and
    `.catch` (a failed options request never leaves an empty stuck dropdown); the filter select/lookup
    loads `.catch`; the permission-matrix and translations sub-loads `.catch` to a rendered
    empty state; the grid/report AJAX fragment swap `.fail`/`.catch`es with a toast; and the grid's
    filter **Apply iterates the rendered `.fk-filter-input`/`.fk-filter-lookup` widgets**, so a
    resource whose `filter_fieldsets` groups only some filters can't throw on Apply.
  - **XSS is defended by default**: the one shared HTML sanitizer lives in
    `fastkit_core.sanitize.sanitize_html` (allow-list tags/attrs/URL schemes, drops `on*`,
    `script`/`style`, `javascript:`/non-image `data:`) — a **self-closed** `<script/>`/`<style/>` drops
    only itself and never enters the skip state, so content after it is not silently truncated;
    `RichTextField` **sanitizes by default**
    (pass `sanitizer=None` to explicitly opt out), and content bodies use the same function — so a
    stored rich value rendered via the detail view's `.html()` can't carry a payload. Grid cells are
    **server-rendered through Jinja autoescape** (the `_grid_macros.cell` macro) — a column only
    renders as markup (`| safe`) when it is marked `html` (i.e. the resource has an author
    `render_<column>`); `formatCells` only re-formats datetime/number cells via jQuery `.text()`,
    never inserting markup. The per-request `window.__FASTKIT__` JSON is escaped (`<`,`>`,`&`,U+2028/9 →
    `\u…`) so a `</script>` inside a translation/brand string can't break out of the inline script.
- **Known follow-ups** (documented, lower priority — do not silently "fix" with gambiarras):
  in-memory `RateLimiter`/`RecaptchaVerifier` sets are per-process and reset on restart (a shared
  store is needed for multi-worker); the database/file cache `increment` does not preserve TTL
  (Redis does); `confirm_image_upload`, the database/file cache `set`, and content
  `set_translation` are check-then-write (fine on SQLite's single writer, want an upsert on
  Postgres); mail counts a breaker-open attempt; S3 reads bypass the retry/breaker. Fix these with
  real atomicity, not workarounds. Also: a genuinely circular **singleton** service graph (A needs
  B needs A) raises `ServiceError` when resolved sequentially but can deadlock under concurrent
  cold-start on the per-key locks — an impossible graph either way, so it is left as a known limit
  rather than fixed with a detector that would risk the container's concurrency correctness. The S3
  storage provider is constructed with an un-entered aioboto3 client (env-gated, untested in CI) —
  it needs a lifecycle to enter/close the client and its own `bucket` setting. Swapping the rate
  limiter / reCAPTCHA verifier for a shared-store implementation is part of the multi-worker
  follow-up (they are collaborators of `AuthService`, not yet settings-selected). The CLI has no
  third-party subcommand mechanism yet (unlike apps/assets/tasks/reports/webhooks). None of these
  are wired half-way — implement them fully when needed.
- **Extensibility contracts** (a consumer extends every subsystem without editing the framework):
  apps + lifecycle hooks (`register_settings/models/services/templates/translations/tasks/admin/
  routers` + `startup/shutdown`) discovered via the `fastkit.apps` entry point; the model / router /
  template registries; the service container; `EventBus`; health + system checks. **Providers are
  pluggable by name** through a `fastkit_core.providers.ProviderRegistry` per subsystem
  (`cache_providers`, `storage_providers`, `mail_providers` ship the built-ins and a project
  registers its own factory, selected by `settings.*.provider`); tasks/webhooks/reports use their
  own registries; vendored front-end libs use the `fastkit.assets` entry point. **Translations are
  fully extensible**: `Translator.add_catalog(locale, {...})` adds keys **or a whole new locale**,
  and `LocaleResolver` consults `translator.supported()` live, so a registered locale is immediately
  resolvable from `Accept-Language` (the framework ships **en + pt** complete; any other locale is a
  consumer catalog). The admin engine is open through `AdminResource` subclassing, custom
  `Field`/`Filter`/`AdminAction`, `AdminSite` registration, `AdminRenderer` override dirs + fill-in
  partials, and the `FastKit`/`FastKitAdmin` client bridges. (Client form **field/filter widgets**
  are the one deliberate closed set — field types are backend-declared; extend cells/headers/
  row-actions/dashboard via `FastKitAdmin`, not the form widget switch.)
- **Resilience** (`fastkit_core.resilience`): `CircuitBreaker`, `RetryPolicy`
  (exponential backoff + jitter) and `run_with_retry(op, policy, breaker=…)`. Used by
  the Redis cache provider, the mail service and the S3 storage provider. External IO
  must degrade gracefully, log the failure and recover on its own.

## Wiring a consumer project

The framework ships the generic wiring so a new project writes only its own apps, models,
resources and business rules — never the boilerplate every FastKit app shares. `examples/demo`
is the reference; the moving parts a project actually assembles:

1. **`settings.py`** — `fastkit_config.load_settings(CONFIG_DIR, environment=…)` layers
   `base.toml` + `<env>.toml` + `FASTKIT__SECTION__FIELD` env overrides.
2. **`main.py`** — `create_application(settings)` builds the FastAPI app and sets
   `app.state.fastkit`; then `mount_admin_static(app)` (`fastkit_admin.pages`) serves the admin
   client **and** every vendored asset package in one call. Mount your own media/static dirs
   alongside.
3. **Your app** — a `FastKitApp` subclass listing `requires` (ordering only) and lifecycle hooks:
   `register_models`, `register_admin` (register resources + menu on the `admin_site`), and
   `register_routers`.
4. **Admin deps — do not hand-write them.** `build_admin_deps(runtime, audit=…)`
   (`fastkit_admin.security`) returns `(deps, security)` fully wired from the runtime
   components: cookie-session auth (cookie name from `settings.auth.session_cookie_name`),
   `authorize`, locale resolution, and `translate` (auto-wired from the runtime translator).
   The returned `AdminSecurity` backs every other router that authenticates a request.
5. **Generic routers ship from their owning packages** — mount them, do not copy them:
   `build_role_router(runtime, security)` (`fastkit_permissions.routers`, role/permission editor),
   `build_content_router(runtime, security)` (`fastkit_content.routers`, per-language content),
   `build_admin_router(site, deps)`, `build_profile_router(...)`, `build_upload_router(...)`,
   `build_admin_pages_router(...)`. Each generic router is duck-typed on `security`; permission
   strings and tenant are parameters with sensible defaults, so authorization policy stays with
   the consumer.
6. **First-class in-process worker** — set `tasks.run_worker` (or `FASTKIT__TASKS__RUN_WORKER=true`)
   and the running server also drains the task queue; register handlers with `registry.task(...)`.

What stays in the consumer project is genuinely app-specific: its models and admin resources,
its menu, its authorization policy (which permission guards what), and endpoints encoding business
rules (e.g. the demo's GDPR export/erase and its `is_staff/is_root` admin login gate).

### Multitenant, per-tenant flexible login

The framework is built so a single deployment serves many tenants that each log in differently
(phone-only here, email-only there, email/phone/cpf/username elsewhere) — **the consumer keeps full
freedom over login policy, the framework provides the generic, tenant-safe machinery**:

- **Any identifier type, extensible at runtime.** `NormalizerRegistry` holds one
  `LoginIdentifierNormalizer` (`type`, `normalize`, `mask`, `validate`) per identifier type;
  `default_registry()` ships email, username, phone, cpf, cnpj and social providers. The registry is
  a **shared component** (`normalizer_registry`) that `AccountService` holds by reference, so a
  consumer app (`requires = ("fastkit.accounts",)`) registers its own type in `register_services`
  via `context.component("normalizer_registry").register(MyNormalizer())` and it is immediately live
  in `identifier_types()`, create/add-identifier, and login — no framework change, any system.
- **Login is type-parameterized and tenant-scoped.** `AuthService.login(identifier_type,
  identifier_value, password, requested_tenant_id=…)` validates the type against the registered set,
  normalizes, then matches within the tenant (see the tenant-scoped-authentication invariant). A user
  may hold several identifiers and log in by any of them; the caller chooses the type.
- **Which methods a given tenant offers is consumer policy, not framework opinion.** The login
  endpoint/form decides which `identifier_type`(s) to accept and render per tenant (the demo's
  `LoginRequest` defaults to `email` for its global admin gate). A tenant naturally restricts its
  methods by which identifiers it issues (a phone-only tenant issues only phone identifiers, so any
  other type simply finds no candidate). The framework deliberately does **not** hardcode a
  per-tenant allowed-types table — that would impose one product model and reduce freedom; a consumer
  that wants an explicit allow-list stores it (e.g. on `Tenant.meta`) and enforces it at its own
  login endpoint.
- **The admin panel is a global superadmin surface by design** (confirmed product decision): it
  manages every tenant's data, gated by the `is_staff`/`is_root` separation — *that* flag is the
  admin's access boundary, not a per-tenant one. So the admin authorizes against a single
  configured `tenant_id` (`build_admin_deps(tenant_id=…)`, default `0`/global) and does **not**
  scope its querysets per logged-in tenant. Multitenancy lives in the **apps' end-user auth** (the
  per-tenant flexible login above), not in the admin. Do not "upgrade" the admin into a per-tenant
  self-service panel — a consumer that needs one wires its own security deps and `get_queryset()`
  (which can read `get_request_context().tenant_id`).

## Database conventions

- Models extend `Base` (`fastkit_db.base`) and opt into mixins: `PrimaryKeyMixin`
  (bigint autoincrement id — `BigInteger().with_variant(Integer, "sqlite")`),
  `TimestampMixin`, `TenantMixin`, `SoftDeleteMixin`, `VersionMixin`, `MetadataMixin`,
  `CreatedByMixin`, `UpdatedByMixin`, `ActiveFlagMixin`.
- Foreign keys are `BigInteger` with `ForeignKey("table.id", ondelete=…)`. **Intra-package
  children always carry a real FK with `ondelete`** so a parent delete cascades (or nulls) at the
  DB — including asset variants/attachments (`CASCADE`) and upload sessions (`SET NULL`). Only
  cross-package references (`Session.user_id`, `*.tenant_id`, `avatar_asset_id`,
  `ContentTranslation.language_id`) omit the FK, since packages install independently.
- SQLite enforces foreign keys (a connect listener runs `PRAGMA foreign_keys=ON`) and
  autoincrements a single INTEGER primary key even under the named-constraint naming
  convention.
- **Tenant-scoped uniqueness holds for the global tenant too.** Because `tenant_id = 0` persists as
  `NULL` and SQL treats `NULL` as distinct in a plain unique constraint, the tenant-scoped uniques
  (`LoginIdentifier`, `Content`, `UserRole`) use a **functional unique index over
  `coalesce(tenant_id, 0)`** — so two global rows with the same key conflict at the DB (and the
  insert-first/catch-`IntegrityError` idempotency works for global rows), on both SQLite and
  Postgres.
- IDs surface as strings in API payloads; the admin coerces numeric string
  identifiers back to int.

## Admin engine (fastkit-admin)

- `AdminResource[Model]` declares `list_columns`, `search_fields`, `filters`,
  `actions`, `ordering`, `form_fields`, `fieldsets`, `inlines`, `permissions`, `select_all`.
  `ordering` is empty by default: when nobody overrides it the grid orders by the
  resource's `pk_field` **descending** (`-pk_field` — newest first), exposed to the client as
  `grid.default_sort`.
  The navbar page title is the resource `label` (set it in the sentence case you want).
- **Fields** (`fields.py`): `TextField`, `TextareaField`, `EmailField`, `URLField`,
  `MaskedField`, `PasswordField`, `NumberField`, `DecimalField`, `BooleanField`,
  `DateField`, `TimeField`, `DateTimeField`, `SelectField`, `MultiSelectField`,
  `RelationField`, `LookupField`, `ColorField`, `JsonField`, `RichTextField`,
  `ImageField`, `FileField`, `PermissionMatrixField`, `TranslationsField`.
  Locale-aware parse/format. Fields with `virtual=True` are not persisted and save
  through their own endpoints. `hide_label=True` renders a field without its label
  (use the fieldset title instead). A `Fieldset(title, [names], description=…)`
  renders `description` as a small hint under the title.
- **File cleanup on delete**: a resource lists `file_fields` and receives a `storage`
  provider + `media_base_url`; deleting a record (single or via the grid's bulk
  delete) removes the referenced objects from storage, best-effort and logged.
- **Django-style overrides** on `AdminResource`: `get_queryset()` returns the base
  SQLAlchemy `select` (filter, join, restrict columns); `render_<column>(row, locale)`
  returns a cell's HTML (marks that column `html` in the schema so the client renders it
  as markup, never escaped); `sort_<column>()` returns the SQLAlchemy expression a column
  sorts by; `pk_field` (default `"id"`) is the column used as the record id in
  payloads, the row checkbox and lookups, so models with a non-`id` primary key work.
- **Record label**: a model may define `display_label(self) -> str` returning the text to
  show for that record. `AdminResource.display(row)` calls it when present, else falls
  back to the pk; it drives the detail/view screen title (not the id) and any column that
  references another entity. A resource can override `display()` for full control.
- **Custom rendering on the detail screen too**: `serialize_detail` returns a `_html` map
  with the output of any `render_<field>` method, so a field shown as a badge/custom cell
  in the grid renders the same way on the view screen (the client uses `_html[name]` when
  present, else the type-formatted value). A **`PermissionMatrixField` renders read-only on the
  detail view** (`renderReadonlyMatrix`) — it fetches its `groups_url`/`value_url` and lists the
  **granted** permissions grouped by module (each with a check), so a role's view screen shows what
  it grants instead of an empty card. Both the matrix (edit) and this read-only view use the same
  lightweight section layout — an uppercase `subheader` + divider + responsive grid, **no nested
  cards**.
- **`resolve(session, rows, locale)`** is an async hook called with the page's rows before
  serialization — bulk-load related entities and stash labels on each row so sync
  `render_<column>` methods stay N+1-free. The demo Activity log uses it to show the user
  and target record **names** (via each model's `display_label()`) instead of their ids.
- **`read_only = True`** makes a resource view-only: `permission_flags` reports
  `can_create/update/delete = False` and `create/update/delete` raise. Bulk delete and
  single delete both go through `delete()` (per record), so file cleanup and DB
  cascades always run — there is no raw delete query.
- **Audit trail**: `AdminDeps.audit(action, resource_type, resource_id)` is called
  after create/update/delete. The demo records those plus login, logout and profile
  changes into `AuditLog` (fastkit-logging) and exposes them through a `read_only`
  Activity log resource. The actor comes from the request context (set when the
  current user resolves).
- **Relation / dependent / lookup selects**: options come from an
  `options_<field>(session, params, locale)` handler on the resource — you decide the
  query and the label. Served by `GET /resources/{r}/options/{field}`; `params`
  contains parent field values (for `depends_on` cascades), plus `q` (lookup search),
  `value` (lookup preload) and `limit`. `LookupField(min_chars=0, initial_limit=10,
  search_limit=20)`: the client opens the dropdown **on focus** with `initial_limit`
  results (no typing needed), then sends `search_limit` while the user searches — the
  handler honours `params["limit"]`. The dropdown is a Tabler `dropdown-menu`.
- **Columns** (`columns.py`): `Column(name, align, sortable, clickable, type)`. Sorting is
  applied per column; override how a column sorts with a `sort_<column>()` method
  returning a SQLAlchemy expression. Render a cell with `render_<column>(row, locale)`.
  `type` (else the mapped field's `field_type`, else `"text"`) drives client-side, locale
  aware cell formatting: `date`/`datetime`/`time` and `number`/`decimal` are sent raw and
  formatted in the browser's locale, `boolean` renders a green check / red ✕ icon, and
  `null`/empty renders a Django-style dash. A `render_<column>` always wins.
- **Filters** (`filters.py`): `TextFilter`, `ExactFilter`, `BooleanFilter`, `NumberFilter`,
  `ChoiceFilter`, `EnumFilter`, `DateFilter`/`TimeFilter`/`DateTimeFilter`/`DateRangeFilter`,
  `MultiChoiceFilter`, plus `SelectFilter(field, choices|options, depends_on)` and
  `LookupFilter(field, options, depends_on, min_chars, initial_limit, search_limit)` — the
  last two reuse the resource's `options_<field>` handler, so selects and autocomplete
  lookups work as filters with `depends_on` cascades. A `filters` list may also contain
  `Fieldset(title, [fields])` entries to group filters; `grid_schema` returns them under
  `filter_fieldsets` and the client renders the filter panel grouped, with Apply/Clear.
- **Grid endpoints**: list, detail, `GET /resources/{r}/{id}/row` (single serialized
  row for JS refresh), create/update/patch/delete, actions, options.
- **Schema**: `grid_schema` exposes columns (each carrying its `field_type`), filters,
  actions, `select_all`, `default_sort`, flags; `form_schema` returns `fieldsets`
  (each rendered as its own card).

## Admin frontend — server-rendered Tabler + jQuery

The admin is **fully server-rendered Jinja templates shipped by fastkit-admin** (Django-admin
style), styled with **Tabler (Bootstrap) + jQuery** served from vendored packages (never a CDN).
**Every screen — login, dashboard, list/grid, form, detail, report, profile — is rendered on the
server** from `pages.py`'s screen dispatch; a **thin jQuery client (`static/app.js`) only enhances
the already-rendered DOM** (boots rich widgets from their `data-*`, submits writes to `/api`, and
swaps the grid/report table via a `?_fragment=table` AJAX call). There is no build step, no SPA
framework, no client-side routing or rendering. Navigation is real page loads (`<a href>`); the
mobile hamburger drawer closes naturally on navigation (Bootstrap `Collapse` from Tabler's JS). The
sidebar renders **exactly like Tabler's `layout-vertical`**: each nav group is a
collapsible `nav-item dropdown` (`nav-link dropdown-toggle` + `data-bs-toggle="dropdown"` +
`data-bs-auto-close="false"`) whose `dropdown-menu` holds the group's resources as
`dropdown-item` links — expanded by default and collapsible per group. Inherit Tabler markup,
do not hand-roll it. **Use Tabler's defaults for everything —
never override its colors, shadows or styles.** `admin.css` holds only a few genuinely-custom
component rules — `.fk-upload-preview`, `.fk-lookup-menu`, the loading affordances
(`.fk-load-spin` select spinner, `.fk-busy` grid/report overlay, `#fk-nav-progress` top bar) and
`.ti.alert-icon` (sizes the icon **font** to match Tabler's SVG alert icon) — there is no
primary-color or shadow override. A consumer may opt into a brand primary color via
`theme={"primary_color": …}` (which sets Tabler's own `--tblr-primary`), but the default is stock
Tabler. Never use Tailwind. **Alerts follow Tabler's real markup** (`alerts.html`): `.alert` is a
flex row, so an alert is `<div class="alert alert-*"><i class="ti ti-… alert-icon"></i><div>text
</div></div>` — an icon (colored by the variant via `.alert-icon`) is **required**, never a bare
text alert (login error, `error.html`). The navbar user-menu link keeps horizontal padding so its
Tabler hover highlight has breathing room (not a tight box).

- **Rendering** (`fastkit_admin/rendering.py`): `AdminRenderer` is a Jinja
  environment with a `ChoiceLoader` that searches consumer override directories
  **before** the package templates. A project customizes the admin the Django way —
  by dropping a same-named file in its own `templates/` dir.
- **Templates** (`fastkit_admin/templates/admin/`) are fragmented so a project
  overrides only the piece it needs. `base.html` composes `partials/head.html`,
  `partials/scripts.html` and the page body; `app.html` composes
  `partials/sidebar.html`, `partials/navbar.html`, `partials/content.html`;
  `login.html` composes `partials/login_card.html`. Repeated markup is generated by
  macros in `macros.html` (`brand`, `nav_menu`) so a rule change in the package does
  not break an overrider. Empty fill-in partials (included with `ignore missing`) let
  you inject content without copying anything: `_extra_head.html`, `_extra_js.html`,
  `_pre_body.html`, `_pre_footer.html`, `_post_footer.html`, `_sidebar_footer.html`,
  `_navbar_end.html`. Template names use underscores; partials live under `partials/`.
- **Pages router** (`fastkit_admin/pages.py`): `build_admin_pages_router` **server-renders every
  screen**. `render_screen` gathers request/user/session then `dispatch_screen` maps the path
  (`resolve_route`) to a screen: `` `` (root)→dashboard, `{resource}`→list, `{resource}/new`→create
  form, `{resource}/{id}/edit`→edit form, `{resource}/{id}`→detail, `reports/{name}`→report,
  `profile`→profile. Each screen is permission-gated (an `AuthorizationError` renders `error.html`
  with 403, not a raw JSON envelope), builds its context via `screens.py` (`list_context`/
  `form_context`/`detail_context`/`report_context`/`profile_context`) and renders. **A
  `?_fragment=table` request renders only `partials/_table.html`/`_report_table.html`** (no shell) —
  that's what the client swaps on grid/report AJAX. A `t(key, **params)` callable (bound to
  `translator.gettext` + the resolved locale, key-fallback) is injected into every render, so
  templates translate everything. `report_data(name, session, locale, params)` and
  `profile_data(user, locale)` are async providers the consumer wires from its report/account
  services (the demo does at `demo_app.py`). The module-level screen builders are unit-tested via
  direct `await` for 100% coverage (route handlers are thin `return await render_*(...)` wrappers).
  `build_page_config` builds the shell context + the per-request `window.__FASTKIT__` client
  bootstrap (api base, admin path, brand, locale, timezone, messages, reCAPTCHA). `STATIC_DIR` holds
  `app.js` + `admin.css` (mount at `/admin-static`).
- **Vendored assets, no CDN** (`fastkit_admin/assets.py`): `AssetRegistry.discover()`
  collects every front-end library from installed `fastkit.assets` entry-point providers
  (each `fastkit-vendor-*` package ships its files under `static/` and declares a `MOUNT`,
  `STATIC_DIR` and ordered `ASSETS` list with `kind` css/js and per-tag `attrs`).
  `build_page_config` puts the ordered `head_assets`/`body_assets` tags in the template
  context and the `asset_link`/`asset_script` macros render them with their attributes
  (e.g. TinyMCE's `referrerpolicy`); `mount_assets(app)` serves each package's files. To
  change a library version, bump its `fastkit-vendor-*` package — templates never name a
  URL. reCAPTCHA is the one intentionally-remote script (it must load from Google).
- **Public UI library** (`static/fastkit-ui.js` → `window.FastKit`): the interface
  layer every consumer talks to, so nobody depends on Tabler/Bootstrap directly.
  `FastKit.toast(kind, msg)`, `FastKit.confirm(opts) → Promise<bool>`,
  `FastKit.modal(opts) → {close}`, `FastKit.alert(msg)`, `FastKit.lightbox(src)`,
  `FastKit.api(method, path, body)`, `FastKit.upload(url, file)`, `FastKit.t(key)`,
  `FastKit.registerMessages`, and **`FastKit.formErrors($scope, err, {aliases})`** (the single
  way to surface API errors on a form — never hand-roll a `.catch`). Build all new UI through
  these — internally they speak low level to Tabler/jQuery. Apply this "public interface, private
  internals" split everywhere it makes sense.
- **Client** (`static/app.js`): a **thin jQuery enhancement layer** (≈700 lines, down from the old
  1373-line SPA renderer) built on `FastKit`. It does **not route or render screens** — the server
  does. On DOM-ready it reads `window.__FASTKIT__`, restores a `sessionStorage` **flash** toast
  (so a "Created"/"Updated" message survives the post-save full-page navigation), fires
  `fastkit:ready` (so `FastKitAdmin` extensions register), and runs per-screen `init*` functions
  that detect their screen by DOM markers (`#grid`, `form[data-resource]`, `#report`, `#dashboard`,
  `[data-testid=profile]`, `#login-form-el`). `enhance(root)` boots the rich widgets **from their
  server-rendered `data-*`**: masks, color, uploads, TinyMCE richtext, JSONEditor, relation/lookup
  selects (options + `depends_on` cascades, value-first on edit), permission-matrix and translations.
  `collect($form)` reads every `.fk-field[data-type]` (skipping the virtual matrix/translations,
  which save through their own endpoints) into a payload — including nested inline rows as
  `{<inline>: [{...}, ...]}` — and submits to `/api`; errors go through `FastKit.formErrors`. The
  grid does **jQuery AJAX**: search/sort/paginate/filter and row-delete/bulk swap the server's
  `?_fragment=table` HTML into `#grid` (never a full reload); datetime/number cells are formatted
  client-side in the user's timezone/locale (`formatCells`, reading each cell's raw value from the
  row's `data-row` JSON). Every destructive action goes behind `FastKit.confirm`. Uploads are keyed
  by kind: `POST /api/uploads/{kind}`. Because navigation is real page loads, there is no client
  render-race to guard.
- **Rich text** is **TinyMCE 7** (self-hosted from `fastkit-vendor-tinymce`, GPL license
  key, no cloud account). `initRichtexts` boots one editor per server-rendered
  `RichTextField` mount on DOM-ready (navigation is a full page load, so editors are torn
  down by the browser and re-init on the fresh page — no SPA disposal); `readField` reads
  content back through `tinymce.get(...)`. Image toolbar uploads go through
  `FastKit.upload(field.upload_url, blob)` → `/api/uploads/image`.
- **JSON fields** use **JSONEditor** (self-hosted from `fastkit-vendor-jsoneditor`, tree +
  text modes). `initJsons` boots one editor per `JsonField` mount on DOM-ready, and
  `readField` returns `editor.get()` (a real object, so the API gets native JSON). The
  detail view shows JSON in a `<pre>`.
- **Inlines — a parent form with infinite repeatable sub-items** (`inlines.py` +
  `partials/inline.html`). `AdminResource.inlines = [InlineResource(name, form_fields, model,
  fk_field, label, min_items, max_items, pk_field="id")]` renders each child sub-form as a
  card of repeatable rows below the parent fieldsets (server-rendered pre-filled on edit via
  `resource.inline_values` → `InlineResource.load`). The client (`initInlines`) clones the
  `<template class="fk-inline-prototype">` on **Add**, removes a row on **Remove** (honouring
  `min_items`/`max_items`), and `reindexInline` keeps input ids unique; `collect` serializes
  every row (with its hidden `fk-inline-id`) into `{<inline>: [{id?, ...}, ...]}`. The parent
  resource **persists children in the same transaction** (`_save_inlines` → `InlineResource.save`):
  an **id-diff formset** — rows with a persisted `pk_field` are updated, new rows inserted, and
  rows no longer present deleted (never delete-then-insert, so a child referenced elsewhere keeps
  its id across an edit). A partial `PATCH` that omits an inline key leaves those children
  untouched. The demo's Categories form manages its Subcategories inline.
- **Grid screen = three decoupled stacked parts** (the toolbar/filters are NOT baked into the
  grid card): (1) a **toolbar card** (`card > card-body > row g-2`) holding the search (only when
  the resource has `search_fields`, in a growing `col-md`) and a right-aligned `btn-list`
  (`col-md-auto ms-md-auto`) with Filters + bulk/collection actions + New — a Bootstrap-grid row
  so it is one line on tablet/desktop and stacks (search on top, buttons beneath) on a phone,
  always inside the viewport; (2) the **filter panel** (its own `card`, `d-none`, toggled by the
  Filters button) that opens **below the toolbar and above the grid**; (3) the **grid card** —
  `table-responsive` > `table table-selectable card-table table-vcenter text-nowrap datatable`,
  then a `card-footer`. Sortable headers
  are a clickable label + a single chevron/`selector` icon (no Tabler `table-sort` class, so
  the icon is never doubled, and the header text stays aligned with the body cells), the
  footer shows `grid.showing` ("Showing X to Y of Z entries") next to **numeric pagination**
  (windowed page numbers with prev/next chevrons). The grid is **server-rendered** (`_table.html` via `list_context`) and its search/sort/paginate/
  filter and row-delete/bulk **swap the `?_fragment=table` HTML into `#grid` by jQuery AJAX** — no
  full reload. Boolean columns (header **and** cells) are **center-aligned by default** (`Column.align`
  is `None`) unless the column sets `align`, and cells render an inline SVG check/✕. The **row-action
  dropdown (a `⋮` button) is marked `fk-menu-fixed` with `data-bs-display="static"`** (so Bootstrap
  does NOT Popper-position it — no `transform`/`inset` to fight); on `shown.bs.dropdown` the client
  positions it `position: fixed` (clearing Popper's `inset`/`transform`, flipping **up** when the
  row is near the viewport bottom), so the menu escapes the table's `overflow` instead of being
  clipped. On `show.bs.dropdown` the client also **stamps the active `data-bs-theme`** onto the menu
  (read from `<html>`) so a floating menu is always self-sufficiently light or dark.
- **Cell formatting** (`formatCells`): a column marked `html` (its resource has a
  `render_<column>`) is rendered as markup, never escaped; otherwise the client formats by
  the column's type — booleans as a green check / red ✕ inline SVG, `date`/`datetime`/`time`
  and `number`/`decimal` in the **user's timezone** (`window.__FASTKIT__.timezone`, injected
  per request from the signed-in user's `timezone`; storage is always UTC and naive UTC
  datetimes are serialized with a `+00:00` offset), `null`/empty as a Django-style dash
  (`—`), everything else as text. The row **selection column only renders when the resource
  has bulk operations**.
- **Row actions are a Tabler dropdown** (a `⋮` icon button — Tabler's `btn btn-action`, whose
  open/hover state uses `--tblr-active-bg` so it stays theme-aware; do **not** use
  `btn-ghost-secondary`, whose active fill is a solid light gray that looks wrong on dark)
  with icon items — **View** (`ti-eye`, when `can_detail`), **Edit** (`ti-edit`,
  `can_update`), custom row actions and extension actions, and **Delete** (`ti-trash`,
  `can_delete`) — space-saving and extensible. **Bulk actions are a dropdown** in the toolbar (delete + `scope="bulk"`
  actions) shown when the resource has bulk ops; **`scope="collection"` actions** render as
  toolbar buttons that run with no selection (the demo Task runs "Enqueue welcome email"
  button enqueues a `fastkit-tasks` job this way).
- **Screen-level permission guard**: every data endpoint checks its permission
  (`list`/`detail`/`create`/`update`/`delete`/action). The **server** also guards each rendered
  screen — `dispatch_screen` calls `check_permission` for the screen's action and renders
  `error.html` with status **403** on `AuthorizationError`, and the toolbar only emits the New/Edit
  affordances when `flags.can_create`/`can_update` — so both the buttons and the screens require
  permission.
- **Filter panel**: when a resource has filters the toolbar shows a **Filters** toggle that
  reveals a panel grouped by the resource's `filter_fieldsets`. Each filter renders the
  widget for its type — text/number/date/datetime/time inputs, a from–to date range,
  boolean and choice/enum selects, an options-backed **select**, and an autocomplete
  **lookup** — with `depends_on` cascades of any depth (resets are recursive, never capped
  at two levels). Apply sends the values to the list endpoint as `filter[field]` (and
  `filter[field][from]`/`[to]` for ranges — the exact shape `parse_grid_query` expects);
  Clear resets them.
- **Dependent selects load value-first**: independent selects load, then each one loads its
  own dependents once its value is set (so an edit form fills every level of a chain), and
  **submit is blocked with a warning while any dependent options are still loading** so a record
  is never saved with cleared fields.
- **Dependent resets cascade recursively to any depth** (`resetDependent` in app.js): changing a
  select/lookup resets its direct children **and re-fires a `change` on each reset child**, so the
  reset propagates down the whole chain — a 4-level `country → state → city → district` chain (or
  deeper) fully clears/reloads every level below the one that changed, never leaving a stale
  grandchild value (a select's programmatic `.val()` fires no native `change`, so the explicit
  re-trigger is what makes N-level chains correct). Applies identically to form selects/lookups and
  to filter-panel select/lookup filters. The demo's **Geo samples** resource runs a real 4-level
  chain to lock this in.
- **Loading feedback is built into every async widget** (`setLoading`/`loadingMenu`/`setBusy` in
  app.js, styled by `admin.css`): while a relation/filter **select** fetches remote options it is
  **disabled** and shows a small Tabler `spinner-border` in the field corner
  (`data-testid=loading-<field>`); while a **lookup** fetches, its dropdown shows a spinner + the
  **translated** `form.loading` message (`data-testid=lookup-loading`, text from the client catalog —
  never a hardcoded English string); the **grid/report** table shows a centered overlay spinner
  (`.fk-busy`, `data-testid=content-loading`) over the card while the `?_fragment=table` AJAX runs,
  cleared when the fragment swaps in (or on `.fail`); and because navigation is a **full page load**,
  a **top progress bar** (`#fk-nav-progress`, `data-testid=nav-progress`) starts the instant any
  internal link is clicked (`initNavProgress` delegates on `a[href]`, skipping AJAX-handled links via
  `event.isDefaultPrevented()`, `#`/external/download/`fk-report-export` links) and while `go()`
  navigates — so a slow server response never leaves the user with zero feedback; it vanishes with the
  old document when the new page renders. The demo's **Geo samples** resource (`geo.py` +
  `GeoSampleAdmin`) exercises all of it: a **4-level** `country → state → city → district` dependent
  chain rendered **both** as `RelationField` selects and `LookupField` lookups (and as `SelectFilter`
  + `LookupFilter` chains in the filter panel), with deliberately slow option handlers and a slow
  `list` so the spinners/overlay/bar are visible.
- **Profile** screen edits the avatar (upload), display/first/last name, password, and the
  user's login methods, all through the profile router. The login-method **Type is a select
  of the account service's registered identifier types** (`identifier_types`), and the
  server validates it (422, never a 500) — wrong current password is also a 422 field error,
  not a 401, so it does not log the user out. Every profile sub-form surfaces **field-level
  errors** through the one shared `FastKit.formErrors($scope, err, {aliases})` helper (the password
  service raises them under `field="password"`, aliased to the `new_password` field), falling
  back to a toast only when no field matched. Saving details **updates the navbar identity live**
  (the client rewrites the `user-name` text) and **uploading a new avatar updates the navbar avatar
  live too** (`[data-testid=user-avatar]` background-image, not only the profile card — no reload
  needed), and the avatar
  **persists**: `_profile_summary` returns a resolved `avatar_url` (the profile router takes an
  `avatar_url(asset_id)` resolver — the demo builds it from `asset_service.get(id).object_key` +
  the storage base URL), which both the profile screen and the header read. The server-rendered
  header also resolves it on load: `build_admin_pages_router(..., avatar_url=…)` fills the navbar
  avatar in `shell_context`, so a full reload shows the photo (not just the live update).
  **Avatars are cropped to a centered square** on upload — the profile uses a dedicated
  `build_avatar_upload_handler` that runs the bytes through `process_variant(mode="cover",
  512×512, webp)` before storing, so a rectangular upload is normalized (the general image
  handler still stores originals untouched).
- **Light / dark theme**: the navbar has a sun/moon toggle (`data-bs-theme` on `<html>` and
  `<body>`, persisted in `localStorage.fk-theme`, applied early in `<head>` to avoid a
  flash). Everything uses Tabler's theme variables, so both themes work everywhere.
- **Reports** (server-rendered `report.html` + `initReport`): **one report = one screen = one menu
  item** (path `{admin}/reports/{name}`) — never several reports on one page. The report screen and
  its `_report_table.html` are rendered by the pages router (`report_context`); `initReport` only
  wires the filter panel and swaps the `?_fragment=table` HTML into `#report` by jQuery AJAX on
  Apply/Clear. **Report filters have full parity with CRUD grid filters** — they ARE the same
  filters: `ReportDefinition.filters` holds the same `fastkit_admin.filters.*` objects (any type —
  text, number, boolean, select, enum, date/range, and `LookupFilter`/`SelectFilter` with `options`
  + `depends_on` cascades), rendered by the **same `_filter_panel.html`** used by the grid and
  enhanced by the **same `enhanceFilters`** client fn (grid and report pass their own options URL
  builder). fastkit-reports never imports fastkit-admin — `ReportDefinition.filters` is a plain
  `list` of `to_schema()`-able objects (duck-typed), and `to_schema()` serializes them, so a
  consumer that has both packages (the demo) passes admin filters straight in. Select/lookup options
  come from `ReportDefinition.options` (`{field: async handler(session, params, locale)}`), served by
  `ReportService.resolve_options` via `/reports/{name}/options/{field}` (mirrors the resource
  `options_<field>` endpoint). Apply flattens the filter values (`field=…`, ranges as
  `field_from`/`field_to`) into the fragment request and re-points the export links. The demo's
  Product-prices report uses Category + Subcategory lookups (cascade) + a Max-price number
  filter, reusing the very same `category_options`/`subcategory_options` handlers as the grid.
  `ReportService.export_formats()` lists the non-screen renderers — the demo adds an
  `fpdf2`-based `PdfRenderer` and ships two reports exporting **CSV, HTML and PDF**. Endpoints:
  `/api/reports`, `/api/reports/{name}/run`, `/api/reports/{name}/options/{field}`,
  `/api/reports/{name}/export.{fmt}` (all accept the filter params as query string).
- **Empty fieldsets are dropped** from a form: a `Fieldset` whose fields are all filtered out
  (e.g. read-only metadata on the create form) is not rendered. The demo Product shows the
  full record on the detail screen (read-only `id`/`created_at`/`updated_at` in a "Record"
  fieldset), which appears on edit/view but not on create.
- **Every screen fills the width** (`container-fluid`, not `container-xl` which left giant side
  padding on wide screens): grid, reports, profile, **and the edit form + detail view all render
  full-width cards** — no per-screen `max-width` wrapper. **Form and detail fields stack in a single
  full-width column** (each field is a `col-12` in the `row`). A two-column field grid (`col-lg-6`)
  was tried and removed: on a wide monitor it threw paired fields far apart and floated a lone
  toggle to the middle, which read as broken. One field per row, each spanning the card, keeps the
  form clean at any width.
- **Save/delete messages are generic per context**, not per screen or field:
  `form.created` / `form.updated` / `form.deleted` (translated), driven by whether the
  form had a record id and by the delete path. On a **validation failure** the save handler
  fills each field's `[data-error]`, then `focusFirstError` scrolls the first errored field's
  wrapper into view (`scrollIntoView({block:"center"})`) and focuses its input — so submitting
  an invalid form never leaves the user stranded at the bottom.
- **APIs live at `/api`** (not `/admin/api`): they are the general, permission-gated
  API. The admin UI is one consumer of it.
- **Login**: posts to `/api/auth/login`; password fields use
  `autocomplete="new-password"` so browsers do not prefill. reCAPTCHA v3 is optional
  (`settings.auth.recaptcha.enabled`) — when on, the token is fetched with
  `grecaptcha.execute` and sent with the login.
- **Translations are backend-concentrated and pushed to the client** (Django-style — one
  authority, the JS holds a copy). The `Translator` (`fastkit-i18n`) is the single source; the
  **pages router injects `translator.messages(locale)` + the resolved `locale`** into
  `window.__FASTKIT__` per request (`render_client_json`), and `FastKit.t(key)` reads that copy
  (`CONFIG.messages[key] || key`) — the client ships **no** embedded catalog. The active locale
  is resolved **on the backend** (`config.forced_locale` else `deps.get_locale(request)` from
  `Accept-Language`/cookie via `LocaleResolver`, which falls back region→base `pt-BR`→`pt`);
  server-rendered strings still use `data-i18n="key"` filled by `FastKit.localize()`.
  - **Keys are `context.local`, kebab-case local part** (e.g. `error.invalid-email`,
    `grid.apply`, `validation.string-too-short`, `login.failed`). Never camelCase, never a deeper
    path.
  - **One catalog per concern, both merged into the one Translator**: framework **error +
    validation** strings live in `fastkit_i18n.catalogs.BASE_CATALOGS` (en + pt, the two complete
    built-in locales) —
    the single place for every `error.*`/`validation.*` string, including auth/assets/mail/storage
    error codes (a boundary test asserts **every** `ErrorCode.translation_key` across all packages
    has a `BASE_CATALOGS["en"]` entry). Admin **UI chrome** lives in `fastkit_admin.messages.
    ADMIN_MESSAGES` and is registered by `AdminApp.register_translations`.
  - **Field-error messages come from the catalog, not inline strings**: a `FieldError` carries a
    `code` (`validation.*`) + `params`; the three exception handlers resolve the message via
    `translator.gettext(code, locale, **params)` (`localize_field_errors`). This covers **every
    FastAPI/pydantic validation error** (`PYDANTIC_CODE_MAP` maps every pydantic v2 error type to
    a `validation.*` key, ctx → params) **and** admin field/normalizer/password validation — all
    translated, no scattered English. `_fail(code)` and normalizers raise code-only. A `FieldError`
    **never carries an inline `message`** and its `code` is a `context.local` **kebab-case-local** key
    (`validation.password-incorrect`, never dotted `validation.password.incorrect`) present in both
    catalogs — a boundary test (`test_every_framework_field_error_code_is_translated`) scans every
    framework `FieldError(...)` in source and fails on a dotted or missing-from-catalog code, so a raw
    key can never surface under a field again.
  - **Resource-declared strings** (author labels: resource/column/filter/fieldset/field titles)
    stay **gettext-style — the English string is its own key** and falls back to itself, translated
    server-side by `resource.translate_schema` (`grid_schema`/`form_schema` take a `translate`)
    and, for the sidebar, by `render_shell`. A consumer wires `AdminDeps(translate=…)` and adds a
    catalog with `translator.add_catalog(locale, {...})` — the demo registers `DEMO_PT` in
    `DemoApp.register_translations`. Column headers are Title-Cased from the field name while field
    labels keep their declared case, so register both forms.
  - **Extensible**: a subproject adds keys or a **whole new locale** by calling
    `translator.add_catalog(locale, {...})` from its own `register_translations` hook — no change
    to the framework. `FastKit.registerMessages(locale, dict)` is the supplementary client hook
    (merges into the active catalog).
- **Theme**: `build_page_config(..., theme=...)` sets brand name, logo (with a max
  height), an optional brand primary color (sets Tabler's `--tblr-primary`, opt-in only) and
  favicon.
- **Dashboard is the home screen**: the admin root (`{admin}`) renders a **dashboard**, not a
  resource grid — the sidebar's first link is Dashboard (`data-resource="dashboard"`). By
  default it shows an empty-state; a project supplies its own via
  `FastKitAdmin.registerDashboard(function (element, ctx) { … })` (the demo renders overview
  stat cards). Each project implements its own dashboard.
- **Enter applies filters**: pressing Enter in any grid-filter or report-filter input submits
  the filter (same as clicking Apply).
- **URLs use dashes, never underscores** — resource names and report names are kebab-case
  (`task-runs`, `report-runs`, `sales-by-category`, `product-prices`), so paths like
  `{admin}/reports/product-prices` never contain an underscore.
- **Extensibility bridge** (`window.FastKitAdmin`): external scripts (jQuery, loaded
  through `_extra_js.html`) can `registerCellRenderer` (may return an HTML string or a
  live jQuery/DOM element for interactive cells), `registerHeaderRenderer`,
  `registerRowAction`, listen to `fastkit:*` events (`cell-click`, `action`, `ready`)
  and call `refreshGrid()` / `refreshRow(id)` to refresh keeping filters and page. The
  demo's `showcase.js` (loaded via a template override) shows badges, computed cells,
  a click-to-edit ajax modal that patches one row, a boolean toggle, and row actions
  that refresh a row or the whole grid.
- **Content** is pyaa-style: `Language` records plus per-key, per-language bodies. The
  demo manages languages and edits content per language with `TranslationsField`
  (backed by `/api/content/languages`, `/api/content/{id}/translations`), and reads
  content filtered by language at `/api/content-by-key/{key}?language=…`.
- **e2e** lives in `frontend/admin` (Playwright only — the Vue app was removed). Its
  webServer seeds and runs the demo; specs cover every field type and screen.

## Testing

- `pytest` runs with `--import-mode=importlib`. **Never** `from conftest import` —
  expose shared models/helpers through fixtures.
- 100% branch coverage per package is mandatory (`make coverage`,
  `--cov-fail-under=100`). Coverage-after-await under httpx/ASGI is not traced —
  extract module-level handlers and unit-test them via direct `await`.
- Browser behaviour is covered by Playwright (`make test-e2e`); it must exercise every
  field type and every screen.
- Integration against real services runs through `docker-compose.yml` and CI. Tests
  that need a live service are gated by env vars (e.g. `FASTKIT_TEST_REDIS_URL`) and
  skip otherwise; connection-failure paths are tested with the real client against a
  dead endpoint so degradation and recovery are exercised.

## Conventions (hard rules)

- `__init__.py` files are **empty**. Import from concrete submodules.
- One statement per line. Single-line function signatures and calls. No statements
  split with semicolons.
- Comments are rare and only where the code cannot speak for itself. Single-line `#`
  and `//` comments are lowercase. Code and comments are in English.
- No legacy or backward-compatibility code. Ship the final version and refactor
  callers. No dead code, no fallbacks-just-in-case, no gambiarras.
- No `TYPE_CHECKING` import guards.
- Utility functions live in a package's **`helpers.py`** — never a module or symbol
  named `util`/`utils`.
- Names carry the meaning: prefer a well-named variable, function or class over a
  comment. Async everywhere for IO.
- Do only what the task genuinely needs. Keep the suite green and 100% covered.

## Common commands

```bash
make install        # venv + every workspace package
make install-admin  # Playwright e2e dependencies
make coverage       # Python suite with the 100% branch-coverage gate
make lint           # ruff (never `ruff format` — it breaks single-line signatures)
make test-e2e       # Playwright browser suite (runs the demo)
make seed           # seed the demo database
make dev            # run the demo API on :8100 (with the in-process task worker)
make worker         # run a standalone task worker (production-style, separate process)
```
