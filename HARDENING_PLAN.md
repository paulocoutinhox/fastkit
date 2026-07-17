# FastKit hardening plan — pydantic v2 100% coverage + full audit

Owner: this task. Do not stop until every item is **implemented, tested (100% branch coverage) and documented in CLAUDE.md**.
No legacy code, no backward-compat shims, no gambiarras, no fallbacks-just-in-case. English code and comments. No semicolon-split statements. Comments rare.

Status legend: `[ ]` todo · `[~]` in progress · `[x]` done · `[test]` covered · `[doc]` documented in CLAUDE.md

---

## PART A — Pydantic v2 100% validation coverage

Goal: every one of the **104** pydantic v2 error types (from `pydantic_core.core_schema.ErrorType`, pydantic 2.13.4 / pydantic_core 2.46.4) resolves to a specific, translated `validation.*` message. Nothing falls silently to the generic `validation.invalid` unless that IS the correct semantic message. No pydantic v1 anywhere.

### A1. Complete `PYDANTIC_CODE_MAP` — `packages/fastkit-core/src/fastkit_core/errors/handlers.py`
- [ ] Replace the current ~40-entry map with an **exhaustive 104-entry map** covering every `ErrorType` literal.
- [ ] Keep `GENERIC_VALIDATION_CODE = "validation.invalid"` only as the defensive default for a future/unknown pydantic type (so a pydantic upgrade can never produce a raw code), NOT as a routine outcome for a known type.
- [ ] Every value in the map must be a key that exists in `BASE_CATALOGS["en"]` and `["pt"]`.

### A2. Add every missing `validation.*` key — `packages/fastkit-i18n/src/fastkit_i18n/catalogs.py` (en + pt)
New keys to add (both locales), with meaningful messages using the correct pydantic ctx params:
- [ ] `validation.recursion` (recursion_loop)
- [ ] `validation.invalid-key` (invalid_key)
- [ ] `validation.frozen` (frozen_field, frozen_instance)
- [ ] `validation.none-required` (none_required)
- [ ] `validation.number-finite` (finite_number)
- [ ] `validation.string-ascii` (string_not_ascii)
- [ ] `validation.too-short` (too_short — ctx min_length)
- [ ] `validation.too-long` (too_long — ctx max_length)
- [ ] `validation.bytes-type` (bytes_type)
- [ ] `validation.bytes-too-short` (bytes_too_short — ctx min_length)
- [ ] `validation.bytes-too-long` (bytes_too_long — ctx max_length)
- [ ] `validation.bytes-encoding` (bytes_invalid_encoding)
- [ ] `validation.date-past` / `validation.date-future` (date_past / date_future)
- [ ] `validation.datetime-past` / `validation.datetime-future`
- [ ] `validation.timezone-naive` / `validation.timezone-aware` / `validation.timezone-offset`
- [ ] `validation.duration-invalid` (time_delta_type / time_delta_parsing)
- [ ] `validation.union-tag` (union_tag_invalid / union_tag_not_found)
- [ ] `validation.url-scheme` (url_scheme)
- [ ] `validation.decimal-max-digits` / `validation.decimal-max-places` / `validation.decimal-whole-digits`
- [ ] Reuse existing keys where semantics match exactly (model_type/dataclass_type/mapping_type → dict-type; tuple/set/frozenset/iterable → list-type; float_type/complex_type → number-type; float_parsing/complex_str_parsing → number-invalid; missing_argument/…only_argument → required; unexpected_*_argument → extra-forbidden; url_* → url-invalid; uuid_* → uuid-invalid; is_instance_of/is_subclass_of/callable_type/value_error/assertion_error/no_such_attribute/needs_python_object/get_attribute_error/default_factory_not_called/missing_sentinel_error/iteration_error/set_item_not_hashable/multiple_argument_values/arguments_type → invalid).

### A3. Completeness test — `packages/fastkit-core/tests` + `packages/fastkit-i18n/tests`
- [ ] Test: **every** literal in `pydantic_core.core_schema.ErrorType` is a key in `PYDANTIC_CODE_MAP` (so a pydantic upgrade that adds a type fails the suite loudly).
- [ ] Test: **every** value in `PYDANTIC_CODE_MAP` exists in both `BASE_CATALOGS["en"]` and `["pt"]`.
- [ ] Test: representative end-to-end validation errors map to the right specific key (extend `test_app_integration.py`).
- [ ] Keep fastkit-core + fastkit-i18n at 100% branch coverage.

---

## PART B — Close the non-validation HTTP error gap (translated envelope for ALL responses)

Currently only `RequestValidationError`, `FastKitError`, `Exception` have handlers. A raw `HTTPException` (404 unknown route, 405 method not allowed, or any dev/middleware-raised `HTTPException`) falls to Starlette's default handler → `{"detail": "..."}` — NOT enveloped, NOT translated.

### B1. New ErrorCodes — `packages/fastkit-core/src/fastkit_core/errors/codes.py`
- [ ] `BAD_REQUEST` (400), `METHOD_NOT_ALLOWED` (405), `NOT_ACCEPTABLE` (406), `PAYLOAD_TOO_LARGE` (413), `UNSUPPORTED_MEDIA_TYPE` (415), and a generic `HTTP_ERROR` fallback. Reuse existing codes for 401/403/404/409/429/503/504.
- [ ] Add their `error.*` translation keys to catalogs (en + pt).

### B2. `starlette_http_exception_handler` — `handlers.py`
- [ ] Map `exc.status_code` → an `ErrorCode` (dict lookup; 4xx-default and 5xx-default fallbacks).
- [ ] Build the envelope via `error_envelope` + `resolve_error_text` so `message.text` is translated and never null.
- [ ] Preserve `exc.headers` on the `JSONResponse` (e.g. `WWW-Authenticate`, `Allow`) — correctness for 401/405.
- [ ] Keep the original `exc.status_code` as the HTTP status.
- [ ] Ignore Starlette's default English `detail` phrase (translated envelope is the single source of truth); document that user-facing custom messages must be raised as `FastKitError`.

### B3. Register the handler — `packages/fastkit-core/src/fastkit_core/app.py`
- [ ] `app.add_exception_handler(StarletteHTTPException, starlette_http_exception_handler)` in `FastKit.install`.

### B4. Tests
- [ ] 404 unknown route → enveloped `resource.not_found`, translated text.
- [ ] 405 wrong method → enveloped `http.method-not-allowed`, `Allow` header preserved.
- [ ] dev-raised `HTTPException(403)` / `HTTPException(418)` (unmapped) → correct status + generic enveloped text.
- [ ] 100% branch coverage on the new handler and code map (including the 4xx/5xx default branches).

---

## PART C — Full project audit (bugs, races, admin-killers, dead/legacy code)

Findings gathered by 5 parallel review agents (core / admin / identity / infra / support). Each confirmed finding becomes a checklist item here with file:line, trigger and fix. Only REAL, reproducible issues — no style, no "show work".

- [x] Collect agent reports (5 agents: core / admin / identity / infra / support).
- [x] Triage: keep only confirmed, reproducible defects. Discard speculative/style findings.
- [x] For each confirmed finding: fix cleanly (no compat shims) + a behavioral test.

### C-findings (triaged from 5 audit agents — only confirmed defects kept)
- [x][test][doc] **C1 sanitize** — self-closed `<script/>`/`<style/>` truncated the rest of the document (`handle_startendtag` entered the skip state and never left it). Fixed: drop-content self-close drops only itself. `sanitize.py`.
- [x][test][doc] **C2 auth timing oracle** — a known passwordless account (`password_hash NULL`) ran neither a real argon2 verify nor `dummy_verify`, leaking its existence by timing. Fixed: `dummy_verify` runs whenever no real verify executed. `auth/service.py`.
- [x][test][doc] **C3 transparent rehash** — advertised but never wired; `needs_rehash` was dead. Fixed: successful login rehashes in place (policy-free `PasswordHashService.rehash`) when argon2 params changed. `auth/service.py`, `auth/passwords.py`.
- [x][test][doc] **C4 permissions duplicate 500** — `grant_permission`/`assign_role` 500'd on a repeat via a raw `IntegrityError`. Fixed: idempotent no-op. `permissions/service.py`.
- [x][test][doc] **C6 admin select 500** — `SelectField`/`MultiSelectField.validate` `TypeError`'d on an unhashable value. Fixed: `isinstance(str)` guard → 422. `admin/fields.py`.
- [x][test][doc] **C7 admin temporal/decimal 500** — Date/Time/DateTime/Decimal parsers 500'd on non-string JSON. Fixed: explicit type guards → 422. `admin/fields.py`.
- [x][test][doc] **C9 task retry policy ignored** — `TaskDefinition.max_attempts/timeout/retry_delay` never reached the execution. Fixed: `TaskQueue` resolves the registry definition as the enqueue default. `tasks/queue.py`, `tasks/app.py`.
- [x][test][doc] **C10 cron Sunday=7** — POSIX `7` weekday raised `CronError` and disabled the schedule. Fixed: accept `7`, normalize to `0`. `tasks/cron.py`.
- [x][test][doc] **C11 log level** — a lowercase level (`warning`) raised `TypeError`. Fixed: resolve via `logging.getLevelName`. `logging/service.py`.
- [x][doc] **SessionService docstring** claimed "rotates" (no such feature) — corrected.

### Audit findings deliberately NOT actioned (with rationale)
- **Dead-code candidates that are public library API** (`fastkit_db.GUID`/`new_uuid`, `fastkit_config.public.is_sensitive_key`/`mask_value`, `fastkit_reports.ReportFilter`, `fastkit_storage.signing.verify`, locale `fallback_chain` defensive tail): these are **library surface offered to consumers**, not dead internal code — a framework not using its own public helper is expected. Left intact.
- **ADMIN date/datetime edit-form round-trip** (a locale-formatted value fed to a native `<input type=date>` renders blank and can NULL the column on save): a **client round-trip** bug in `admin.js`/`serialize_detail`. Deferred: it lives in the frontend layer the user set aside ("esquece a questão visual") and the admin is under an in-progress server-rendered rewrite (`REWRITE_PLAN.md`) that replaces this path. Flagged to the user, not silently dropped.

### Environment note
- `packages/fastkit-db/tests/test_db.py::test_non_sqlite_dialect_skips_pragma` needed `asyncpg`, which was missing from the local venv (pre-existing, unrelated to these changes). Installed it so `make coverage` runs the full suite green.

---

## PART D — Documentation

- [ ] Update `CLAUDE.md`:
  - [ ] Envelope/handlers section: note the full pydantic-v2 coverage + the completeness tests.
  - [ ] New invariant: **every HTTP error is enveloped and translated** (the `StarletteHTTPException` handler), custom user text via `FastKitError`.
  - [ ] Any invariant added/changed by the audit fixes.
- [ ] Keep memory index updated if a durable fact changed.

---

## PART E — Final verification (do not declare done until all pass)

- [ ] `make lint` clean (ruff, never `ruff format`).
- [ ] `make coverage` — full suite, `--cov-fail-under=100`, green.
- [ ] Re-read this file top to bottom: every box checked, tested, documented.
- [ ] Remove this plan file only if the user wants it gone (otherwise leave as record).
