"""The Jinja of the site, where a tenant answers with its own file and the shared one answers for the rest."""

import logging
from functools import partial

from jinja2 import ChoiceLoader, Environment, FileSystemLoader, StrictUndefined, TemplateNotFound, select_autoescape

from helpers.i18n import current_locale, translate
from helpers.money import money, number
from helpers.settings import settings

# An environment carries a compiled cache, so it is built once per tenant and kept.
ENVIRONMENTS: dict[str | None, Environment] = {}

logger = logging.getLogger(__name__)


def build_environment(tenant_code: str | None) -> Environment:
    """A tenant answers with its own file when it has one, and falls back to the shared one when it does not."""
    folders = [settings.templates_dir / "tenants" / tenant_code] if tenant_code else []
    folders.append(settings.templates_dir / "global")

    return Environment(loader=ChoiceLoader([FileSystemLoader(folder) for folder in folders]), autoescape=select_autoescape(["html"]), undefined=StrictUndefined)


def environment_for(tenant_code: str | None) -> Environment:
    if tenant_code not in ENVIRONMENTS:
        ENVIRONMENTS[tenant_code] = build_environment(tenant_code)

    return ENVIRONMENTS[tenant_code]


def render(name: str, tenant_code: str | None = None, context: dict | None = None) -> str:
    """The template is the structure and the catalog is the words, so one file answers in every language."""
    template = environment_for(tenant_code).get_template(name)

    language = current_locale.get()

    # The context is a dict and never keywords, so a caller naming `brand` or `t` never collides with what the frame gives.
    return template.render({"t": translate, "language": language, "money": partial(money, locale=language), "number": partial(number, locale=language), **(context or {})})


__all__ = ["ENVIRONMENTS", "TemplateNotFound", "render"]
