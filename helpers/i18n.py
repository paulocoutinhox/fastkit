"""Which language a caller is answered in, and the catalogue that answers."""

import json
from contextvars import ContextVar

from helpers.settings import settings

LOCALE_DIR = settings.base_dir / "locale"

current_locale: ContextVar[str] = ContextVar("current_locale", default=settings.default_language)

catalogs: dict[str, dict[str, str]] = {language: json.loads((LOCALE_DIR / f"{language}.json").read_text(encoding="utf-8")) for language in settings.supported_languages}


def resolve_locale(accept_language: str | None) -> str:
    """The header is scanned in order and the first supported language wins, quality values included."""
    if not accept_language:
        return settings.default_language

    for chunk in accept_language.split(","):
        code = chunk.split(";")[0].strip().lower().replace("_", "-")

        if not code:
            continue

        if code in catalogs:
            return code

        primary = code.split("-")[0]

        if primary in catalogs:
            return primary

    return settings.default_language


def translate(key: str, locale: str | None = None, **params) -> str:
    language = locale or current_locale.get()
    message = catalogs.get(language, {}).get(key) or catalogs[settings.default_language].get(key, key)

    if not params:
        return message

    return message.format(**params)
