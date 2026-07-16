from fastkit_i18n.locale import base_of, normalize, parse_accept_language


class LocaleResolver:
    """Resolves the active locale from user, tenant, cookie, header and default in order.

    ``supported`` is a callable returning the currently supported locales, so a locale
    registered later through ``Translator.add_catalog`` becomes resolvable without rewiring.
    """

    def __init__(self, supported, default_locale: str = "en"):
        self._supported = supported
        self._default_locale = normalize(default_locale)

    def _current(self) -> set[str]:
        return {normalize(locale) for locale in self._supported()} | {self._default_locale}

    def _pick(self, locale: str | None) -> str | None:
        if locale is None:
            return None

        supported = self._current()
        normalized = normalize(locale)

        if normalized in supported:
            return normalized

        base = base_of(normalized)

        return base if base in supported else None

    def resolve(self, user_locale: str | None = None, tenant_locale: str | None = None, cookie_locale: str | None = None, accept_language: str | None = None) -> str:
        for candidate in (user_locale, tenant_locale, cookie_locale):
            picked = self._pick(candidate)

            if picked is not None:
                return picked

        if accept_language:
            for header_locale in parse_accept_language(accept_language):
                picked = self._pick(header_locale)

                if picked is not None:
                    return picked

        return self._default_locale
