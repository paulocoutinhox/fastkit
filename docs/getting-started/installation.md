# Installation

## Requirements

- **Python 3.12** (the workspace pins 3.12).
- **[uv](https://github.com/astral-sh/uv)** for the virtualenv and editable installs.
- **Node.js + npm** only if you want to run the Playwright end-to-end suite.
- Optional services for integration testing: **PostgreSQL** (a `docker-compose.yml` ships it).

## Set up the workspace

```bash
make install        # uv venv (3.12) + every workspace package, editable
make install-admin  # Playwright e2e dependencies (Node)
```

`make install` creates `.venv` and installs every `packages/fastkit-*` distribution plus the demo,
along with the runtime dependencies (uvicorn, argon2, pyjwt, pillow, jinja2, asyncpg).

## Everyday commands

| Command | What it does |
|---|---|
| `make dev` | Run the reference demo API on `:8100` (with the in-process task worker). |
| `make worker` | Run a standalone task worker (production-style, separate process). |
| `make seed` | Seed the demo database. |
| `make coverage` | Run the Python suite with the **100% branch-coverage gate**. |
| `make lint` | Lint with ruff (never `ruff format` — it breaks single-line signatures). |
| `make test-e2e` | Run the Playwright browser suite (boots the demo). |
| `make test` | Run the Python test suite without the coverage gate. |
| `make test-package PACKAGE=fastkit-core` | Run one package's tests. |

## Installing a single package into your own project

FastKit packages are ordinary distributions. In your project you depend on exactly the packages you
use, for example:

```toml
# pyproject.toml (your project)
[project]
dependencies = [
  "fastkit-core",
  "fastkit-config",
  "fastkit-db",
  "fastkit-admin",
  "fastkit-auth",
  "fastkit-accounts",
  "fastkit-permissions",
  # …only what you need
]
```

Your project then declares its own `FastKitApp` and lists the framework apps it needs in `requires`
(see [Project setup](project-setup.md)).

## Integration services

`docker-compose.yml` provides Postgres for local integration testing. Tests that need a
live service are gated by environment variables (for example `FASTKIT_TEST_POSTGRES_URL`) and skip when
the variable is unset — so the default suite runs entirely on SQLite with no external dependencies.
