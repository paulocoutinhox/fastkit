import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from fastkit_core.context.request import get_request_context


class JsonLogFormatter(logging.Formatter):
    """Renders one JSON object per line enriched with the current request context."""

    def format(self, record: logging.LogRecord) -> str:
        context = get_request_context()

        payload = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": context.request_id,
            "tenant_id": context.tenant_id,
            "user_id": context.user_id,
        }

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, separators=(",", ":"))


def build_file_handler(file_path: str, json_format: bool) -> RotatingFileHandler:
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    handler = RotatingFileHandler(path, maxBytes=5_000_000, backupCount=5, encoding="utf-8")

    if json_format:
        handler.setFormatter(JsonLogFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))

    return handler


def setup_logging(level: str, file_path: str, environment: str) -> logging.Logger:
    """Configure the root logger with a rotating app.log, JSON in stage and prod."""

    json_format = environment in ("stage", "prod")

    root = logging.getLogger()
    root.setLevel(level)

    for existing in list(root.handlers):
        root.removeHandler(existing)

    root.addHandler(build_file_handler(file_path, json_format))

    console = logging.StreamHandler()
    console.setFormatter(JsonLogFormatter() if json_format else logging.Formatter("%(levelname)s %(name)s %(message)s"))
    root.addHandler(console)

    return root
