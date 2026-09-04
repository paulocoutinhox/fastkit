"""The one thing the environment says, which is which configuration to load."""

import importlib
import os

from config.base import Settings

APP_ENV = os.environ.get("APP_ENV", "dev")


def load() -> Settings:
    module = importlib.import_module(f"config.{APP_ENV}")

    return module.settings


settings = load()
