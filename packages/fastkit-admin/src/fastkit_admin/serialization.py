from datetime import date, datetime, time, timezone
from decimal import Decimal

CLIENT_FORMATTED_TYPES = {"boolean", "date", "datetime", "time", "number", "decimal"}

TRANSLATABLE_KEYS = {"label", "title", "description", "help_text", "placeholder", "confirm_message"}


def translate_schema(node, translate) -> None:
    """Translate every display string (label/title/description) in a schema tree in place."""

    if isinstance(node, dict):
        for key, value in node.items():
            if key in TRANSLATABLE_KEYS and isinstance(value, str) and value:
                node[key] = translate(value)
            else:
                translate_schema(value, translate)
    elif isinstance(node, list):
        for item in node:
            translate_schema(item, translate)


def plain_value(value):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value

    return str(value)


def grid_value(value):
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)

        return value.isoformat()

    if isinstance(value, (date, time)):
        return value.isoformat()

    if isinstance(value, Decimal):
        return str(value)

    return plain_value(value)


def coerce_identifier(identifier):
    if isinstance(identifier, str) and identifier.lstrip("-").isdigit():
        return int(identifier)

    return identifier
