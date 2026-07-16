from pathlib import Path

from fastkit_config.loader import load_settings

CONFIG_DIR = Path(__file__).resolve().parents[1] / "config"


def get_settings(environment: str | None = None):
    return load_settings(CONFIG_DIR, environment=environment)
