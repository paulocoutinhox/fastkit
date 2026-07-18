from dataclasses import dataclass

from jinja2 import Environment, FileSystemLoader, TemplateNotFound, select_autoescape

from fastkit_core.errors.exceptions import FastKitError
from fastkit_mail.errors import TEMPLATE_NOT_FOUND


@dataclass(frozen=True)
class RenderedEmail:
    subject: str
    html_body: str
    text_body: str
    template_path: str


class MailTemplateRenderer:
    """Resolves an email template by key, letting a project override any template by dropping a
    same-named file in an earlier search directory."""

    def __init__(self, search_dirs: list[str]):
        self._environment = Environment(
            loader=FileSystemLoader(search_dirs),
            autoescape=select_autoescape(["html"]),
            enable_async=False,
        )

    def render(
        self, template_key: str, context: dict, locale: str = "en"
    ) -> RenderedEmail:
        base_path = template_key.replace(".", "/")
        merged = {**context, "locale": locale}

        try:
            subject = (
                self._environment.get_template(f"{base_path}/subject.txt")
                .render(merged)
                .strip()
            )
            html = self._environment.get_template(f"{base_path}/body.html").render(
                merged
            )
            text = self._environment.get_template(f"{base_path}/body.txt").render(
                merged
            )
        except TemplateNotFound as error:
            raise FastKitError(
                TEMPLATE_NOT_FOUND, message=f"email template '{base_path}' is missing"
            ) from error

        return RenderedEmail(
            subject=subject, html_body=html, text_body=text, template_path=base_path
        )
