"""Which language a caller is answered in, and the catalogue that answers."""

import json
import re
from contextvars import ContextVar

from helpers.settings import settings

LOCALE_DIR = settings.base_dir / "locale"

# What RFC 9110 lets a weight be, which also keeps a value like `nan` from ranking anything.
QUALITY = re.compile(r"0(\.\d{0,3})?|1(\.0{0,3})?")

current_locale: ContextVar[str] = ContextVar("current_locale", default=settings.default_language)

catalogs: dict[str, dict[str, str]] = {language: json.loads((LOCALE_DIR / f"{language}.json").read_text(encoding="utf-8")) for language in settings.languages}


def preferred(accept_language: str) -> list[str]:
    """The languages of the header from the most wanted down, where a weight of zero or one that is not a weight is not a choice."""
    ranked = []

    for chunk in accept_language.split(","):
        code, *parameters = [part.strip() for part in chunk.split(";")]
        weight = 1.0

        for parameter in parameters:
            name, _, value = parameter.partition("=")

            if name.strip().lower() == "q":
                weight = float(value.strip()) if QUALITY.fullmatch(value.strip()) else 0.0

        if code and weight > 0:
            ranked.append((weight, code.lower().replace("_", "-")))

    # The sort is stable, so languages of the same weight keep the order the header gave them.
    return [code for _, code in sorted(ranked, key=lambda entry: entry[0], reverse=True)]


def resolve_locale(accept_language: str | None) -> str:
    """The most wanted language this instance speaks, read by its weight and then by its order."""
    if not accept_language:
        return settings.default_language

    for code in preferred(accept_language):
        if code in catalogs:
            return code

        primary = code.split("-")[0]

        if primary in catalogs:
            return primary

    return settings.default_language


def translate(key: str, locale: str | None = None, **params) -> str:
    """A message of the catalogue of the reader, read by its key: every catalogue carries every key, so a missing one fails where it was written instead of showing its name."""
    message = catalogs[locale or current_locale.get()][key]

    if not params:
        return message

    return message.format(**params)
