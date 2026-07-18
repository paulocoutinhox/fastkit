# fastkit-config

Typed settings from TOML + environment, and a safe public config export.

## Load settings

```python
from fastkit_config import load_settings

settings = load_settings("config", environment="prod")
```

Layers `base.toml` + `<env>.toml` + `FASTKIT__SECTION__FIELD` env overrides. See
[Configuration](../getting-started/configuration.md) and the
[Settings reference](../reference/settings.md).

## Safe public config

```python
from fastkit_config.public import public_frontend_config

public = public_frontend_config(settings)   # never leaks secrets
```

Keys containing `secret`/`password`/`token`/`key` are excluded; `is_sensitive_key` and `mask_value`
are exposed for your own masking.

## Robustness

An env override that descends into a scalar (`FASTKIT__A__B` where `A.B` is a value) overwrites the
node so it surfaces a Pydantic `ValidationError`, never a bare `TypeError` from walking into a `str`.
