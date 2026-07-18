# Configuration

FastKit settings are typed (Pydantic) and layered from three sources, in increasing precedence:

1. `config/base.toml`
2. `config/<environment>.toml`
3. `FASTKIT__SECTION__FIELD` environment variables

```python
from fastkit_config import load_settings

settings = load_settings("config", environment="prod")
```

## Environment overrides

Any setting can be overridden with an environment variable using `__` as the path separator, in
upper case:

```bash
FASTKIT__TASKS__RUN_WORKER=true
FASTKIT__AUTH__CAPTCHA__PROVIDER=recaptcha
FASTKIT__AUTH__CAPTCHA__SITE_KEY=6Lc…
FASTKIT__STORAGE__PROVIDER=s3
FASTKIT__CACHE__PROVIDER=database
```

An override that descends into a scalar (`FASTKIT__A__B` where `A.B` is a value) overwrites the node
so it surfaces a Pydantic `ValidationError`, never a bare `TypeError`.

## The settings tree

The main sections (see the full [Settings reference](../reference/settings.md)):

| Section | Highlights |
|---|---|
| `app` | `name`, `environment`, `secret_key` |
| `database` | `url`, `pool_pre_ping`, `pool_recycle`, `echo` |
| `admin` | `path` (`/admin`), `api_path` (`/api`), `page_size` |
| `auth` | `session_cookie_name`, password length bounds, JWT, lockout, rate limit, `login_identifier_types`, and `captcha` (`provider` = `disabled`/`recaptcha`/`image` + provider fields) |
| `cache` | `provider` (`file`/`database`), `default_ttl_seconds`, `directory` |
| `storage` | `provider` (`local`/`s3`), `base_url`, backend fields |
| `tasks` | `run_worker`, `worker_id`, `worker_queues`, `poll_interval_seconds` |
| `i18n` | `default_locale`, `supported_locales`, `forced_locale` |
| `content` | `sanitize_html` |

## Safe public config

`public_frontend_config(settings)` returns only the values that are safe to expose to a browser (it
never leaks secrets — keys containing `secret`/`password`/`token`/`key` are excluded). It surfaces
the environment, admin API base URL, locale info, a lightweight `captcha` block (provider + public
site key) and feature flags. The admin's own client bootstrap is richer and comes from
`build_page_config` (see [Client](../admin/client-js.md)).

## Wiring config into the app

`load_settings` in `settings.py`, then `create_application(settings)` in `main.py` — the runtime
reads settings during bootstrap and exposes them to every app hook via `context.settings`. See
[Project setup](project-setup.md).
