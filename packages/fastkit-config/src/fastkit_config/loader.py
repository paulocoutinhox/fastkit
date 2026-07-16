import os
import tomllib
from pathlib import Path

from fastkit_config.settings import FastKitSettings

VALID_ENVIRONMENTS = ("dev", "stage", "prod", "test")


class ConfigError(RuntimeError):
    pass


def _read_toml(path: Path) -> dict:
    if not path.exists():
        return {}

    with path.open("rb") as handle:
        return tomllib.load(handle)


def _deep_merge(base: dict, override: dict) -> dict:
    result = dict(base)

    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value

    return result


def _coerce(raw: str):
    lowered = raw.lower()

    if lowered in ("true", "false"):
        return lowered == "true"

    if raw.isdigit():
        return int(raw)

    return raw


def _apply_env_overrides(data: dict, environ: dict, prefix: str = "FASTKIT__") -> dict:
    result = dict(data)

    for key, value in environ.items():
        if not key.startswith(prefix):
            continue

        path = key[len(prefix):].lower().split("__")
        cursor = result

        for part in path[:-1]:
            node = cursor.get(part)

            if not isinstance(node, dict):
                node = cursor[part] = {}

            cursor = node

        cursor[path[-1]] = _coerce(value)

    return result


def load_settings(config_dir: str | Path, environment: str | None = None, environ: dict | None = None) -> FastKitSettings:
    """Merge base.toml, the environment file and FASTKIT__ prefixed variables into typed settings."""

    environ = environ if environ is not None else dict(os.environ)
    environment = environment or environ.get("APP_ENV", "dev")

    if environment not in VALID_ENVIRONMENTS:
        raise ConfigError(f"unknown environment '{environment}', expected one of {VALID_ENVIRONMENTS}")

    directory = Path(config_dir)

    merged = _deep_merge(_read_toml(directory / "base.toml"), _read_toml(directory / f"{environment}.toml"))
    merged = _apply_env_overrides(merged, environ)
    merged.setdefault("app", {})["environment"] = environment

    return FastKitSettings.model_validate(merged)
