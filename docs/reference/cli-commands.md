# CLI and make commands

## Make targets

| Command | Purpose |
|---|---|
| `make install` | uv venv (3.12) + every workspace package (editable) + runtime deps. |
| `make install-admin` | Playwright e2e dependencies (Node). |
| `make dev` | Run the demo API on `:8100` (with the in-process task worker). |
| `make worker` | Run a standalone task worker (production-style, separate process). |
| `make seed` | Seed the demo database. |
| `make coverage` | Python suite with the **100% branch-coverage gate**. |
| `make test` | Python suite without the gate. |
| `make test-package PACKAGE=fastkit-core` | Run one package's tests. |
| `make lint` | ruff (never `ruff format` — it breaks single-line signatures). |
| `make test-e2e` | Playwright browser suite (boots the demo). |
| `make clean` | Remove build/coverage artifacts. |

## The `fastkit` CLI

Boots the runtime and runs administrative operations against it (create a superuser, seed, …), using
the same components the app uses:

```bash
fastkit createsuperuser --email root@example.com
```

The CLI does not yet have a third-party subcommand mechanism (a documented follow-up). See the
[cli package](../packages/cli.md).

## CI

`.github/workflows/ci.yml` runs the lint + coverage gate and the Playwright suite. It uses `make
install` — there is no `requirements.txt`; the workspace is uv-managed and editable.
