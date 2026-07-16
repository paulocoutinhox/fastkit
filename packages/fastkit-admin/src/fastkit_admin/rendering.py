from pathlib import Path

from jinja2 import ChoiceLoader, Environment, FileSystemLoader, select_autoescape

PACKAGE_TEMPLATES = Path(__file__).parent / "templates"


class AdminRenderer:
    """Renders admin pages through Jinja with consumer-first template overrides.

    Consumer directories are searched before the package templates, so a project
    overrides any page (``admin/base.html``) or fills an empty extension partial
    (``admin/_extra_head.html``) just by placing a same-named file in its own
    templates directory.
    """

    def __init__(self, override_dirs: list[str] | None = None):
        loaders = [FileSystemLoader(str(directory)) for directory in override_dirs or []]
        loaders.append(FileSystemLoader(str(PACKAGE_TEMPLATES)))

        self.environment = Environment(loader=ChoiceLoader(loaders), autoescape=select_autoescape(["html"]))

    def render(self, template: str, **context) -> str:
        return self.environment.get_template(template).render(**context)
