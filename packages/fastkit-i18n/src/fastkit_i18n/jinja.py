def install_i18n(environment, translator) -> None:
    """Expose `_` and `gettext`/`ngettext` in a Jinja environment using the translator."""

    environment.globals["_"] = translator.gettext
    environment.globals["gettext"] = translator.gettext
    environment.globals["ngettext"] = translator.ngettext
