# Settings reference

Settings load from `base.toml` + `<env>.toml` + `FASTKIT__SECTION__FIELD` env overrides (see
[Configuration](../getting-started/configuration.md)). Every field is overridable by environment.

## `app`

| Field | Default |
|---|---|
| `name` | project name |
| `environment` | `dev` |
| `secret_key` | (required for JWT) |

## `database`

`url`, `pool_pre_ping` (`true`), `pool_recycle`, `echo`.

## `admin`

`enabled` (`true`), `path` (`/admin`), `api_path` (`/api`), `theme` (`tabler`), `page_size` (`25`),
`page_size_options` (`[10, 25, 50, 100]`).

## `auth`

| Field | Default |
|---|---|
| `login_identifier_types` | `["email", "username", "phone"]` |
| `session_cookie_name` | `fastkit_session` |
| `password_min_length` / `password_max_length` | `12` / `128` |
| `jwt_algorithm` | `HS256` |
| `access_token_ttl_seconds` | `3600` |
| `max_failed_logins` / `lockout_seconds` | `5` / `900` |
| `rate_limit_per_minute` | `10` |

### `auth.captcha`

| Field | Default |
|---|---|
| `provider` | `disabled` (`disabled` / `recaptcha` / `image`) |
| `site_key` / `secret_key` | `""` |
| `action` | `admin_login` |
| `minimum_score` | `0.5` |
| `allowed_hostnames` | `[]` |
| `timeout_seconds` | `5` |
| `image_length` | `5` |
| `challenge_ttl_seconds` | `300` |

## `cache`

`provider` (`file` / `database`), `default_ttl_seconds` (`300`), `directory`.

## `storage`

`provider` (`local` / `s3`), `base_url`, and backend fields (`directory`; or `bucket`, `region`,
`endpoint_url`, credentials for S3). See
[Configure storage](../guides/configure-storage-local-s3-r2.md).

## `tasks`

`run_worker` (`false`), `worker_id`, `worker_queues`, `worker_lease_seconds`, `poll_interval_seconds`.

## `i18n`

`default_locale`, `supported_locales`, `forced_locale`.

## `content`

`sanitize_html`.

## Root

`installed_apps` — the list of app names to bootstrap (their entry points must be discoverable).
