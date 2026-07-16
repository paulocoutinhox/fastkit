from contextvars import ContextVar

_current_locale: ContextVar[str] = ContextVar("fastkit_locale", default="en")


def get_locale() -> str:
    return _current_locale.get()


def set_locale(locale: str):
    return _current_locale.set(locale)


def reset_locale(token) -> None:
    _current_locale.reset(token)


def normalize(locale: str) -> str:
    cleaned = locale.strip().replace("-", "_")
    parts = cleaned.split("_", 1)

    if len(parts) == 1:
        return parts[0].lower()

    return f"{parts[0].lower()}_{parts[1].upper()}"


def base_of(locale: str) -> str:
    return normalize(locale).split("_", 1)[0]


def fallback_chain(locale: str, supported: list[str], default_locale: str) -> list[str]:
    """Return the ordered lookup chain for a locale, filtered to supported locales."""

    normalized = normalize(locale)
    candidates = [normalized, base_of(normalized), default_locale]

    supported_set = {normalize(item) for item in supported} | {default_locale}
    chain: list[str] = []

    for candidate in candidates:
        if candidate in supported_set and candidate not in chain:
            chain.append(candidate)

    return chain or [default_locale]


def parse_accept_language(header: str) -> list[str]:
    """Parse an Accept-Language header into locales ordered by descending quality."""

    entries = []

    for part in header.split(","):
        token = part.strip()

        if not token:
            continue

        if ";q=" in token:
            value, quality = token.split(";q=", 1)

            try:
                entries.append((normalize(value), float(quality)))
            except ValueError:
                continue
        else:
            entries.append((normalize(token), 1.0))

    entries.sort(key=lambda item: -item[1])

    return [locale for locale, _ in entries]
