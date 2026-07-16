# fastkit-config

Typed settings for FastKit, merged from layered TOML files and environment
variables and validated with Pydantic.

## Installation

```bash
pip install fastkit-config
```

## Environments

Valid environments are `dev`, `stage`, `prod` and `test`. The active environment
comes from the `environment` argument or the `APP_ENV` variable.

## Load order

```
base.toml -> {environment}.toml -> FASTKIT__ environment variables
```

Later sources win. Nested keys use `__` as the separator, for example
`FASTKIT__AUTH__PASSWORD_MIN_LENGTH=20`.

```python
from fastkit_config.loader import load_settings

settings = load_settings("config", environment="prod")
```

## Public frontend config

`public_frontend_config` exposes only values that are safe for the browser.
Secrets are never included, and `mask_value` / `is_sensitive_key` help redact
sensitive fields in diagnostics.

```python
from fastkit_config.public import public_frontend_config

payload = public_frontend_config(settings)
```

## Testing

100% branch coverage.

```bash
pytest packages/fastkit-config --cov=fastkit_config --cov-branch
```
