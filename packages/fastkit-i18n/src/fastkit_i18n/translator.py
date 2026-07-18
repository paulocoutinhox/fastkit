from contextlib import contextmanager

from fastkit_i18n.locale import (
    fallback_chain,
    get_locale,
    normalize,
    reset_locale,
    set_locale,
)


class _LenientParams(dict):
    def __missing__(self, key):
        return "{" + key + "}"


def _format(template: str, params: dict) -> str:
    if not params:
        return template

    try:
        return template.format_map(_LenientParams(params))
    except (ValueError, IndexError):
        return template


class Translator:
    """Modular, dictionary-backed translator.

    Any app or the consumer project can register keys for an existing or a brand
    new locale through ``add_catalog``, which also registers the locale so it can
    be resolved.
    """

    def __init__(
        self,
        catalogs: dict[str, dict[str, str]],
        supported: list[str],
        default_locale: str = "en",
    ):
        self._default_locale = normalize(default_locale)
        self._catalogs = {
            normalize(locale): dict(messages) for locale, messages in catalogs.items()
        }
        self._supported = (
            {normalize(locale) for locale in supported}
            | {self._default_locale}
            | set(self._catalogs)
        )

    def add_catalog(self, locale: str, messages: dict[str, str]) -> None:
        """Merge new keys into a locale, creating and registering the locale if needed."""

        normalized = normalize(locale)
        self._catalogs.setdefault(normalized, {}).update(messages)
        self._supported.add(normalized)

    def supported(self) -> list[str]:
        return sorted(self._supported)

    def gettext(self, key: str, locale: str | None = None, **params) -> str:
        active = normalize(locale or get_locale())

        for candidate in fallback_chain(active, self.supported(), self._default_locale):
            catalog = self._catalogs.get(candidate)

            if catalog is not None and key in catalog:
                return _format(catalog[key], params)

        return key

    def ngettext(
        self,
        singular_key: str,
        plural_key: str,
        count: int,
        locale: str | None = None,
        **params,
    ) -> str:
        key = singular_key if count == 1 else plural_key

        return self.gettext(key, locale=locale, count=count, **params)

    def messages(self, locale: str) -> dict[str, str]:
        """Return the full catalog for a locale, resolved through its fallback chain.

        This is what a frontend receives so it can translate its own keys.
        """

        merged: dict[str, str] = {}

        for candidate in reversed(
            fallback_chain(normalize(locale), self.supported(), self._default_locale)
        ):
            merged.update(self._catalogs.get(candidate, {}))

        return merged

    @contextmanager
    def activate(self, locale: str):
        token = set_locale(normalize(locale))

        try:
            yield
        finally:
            reset_locale(token)
