# fastkit-testkit

Shared testing utilities so packages and consumer projects test the same way.

## What it provides

- **`clock`** — a controllable clock for deterministic time in tests (advance it instead of sleeping).
- **`database`** — an in-memory / temp SQLite database fixture.
- **`factories`** — builders for common models.
- **`providers`** — fake/recording providers (cache, storage, mail) for tests.
- **`asserts`** — envelope and error assertions.

## Testing rules (framework-wide)

- `pytest` runs with `--import-mode=importlib`. **Never** `from conftest import` — expose shared
  models/helpers through fixtures.
- 100% branch coverage per package is mandatory (`make coverage`, `--cov-fail-under=100`).
  Coverage-after-await under httpx/ASGI is not traced — extract module-level handlers and unit-test
  them via direct `await`.
- Tests that need a live service (Postgres) are gated by env vars and skip otherwise;
  connection-failure paths are tested with the real client against a dead endpoint.
- Browser behaviour is covered by Playwright (`make test-e2e`), exercising every field type and screen.
