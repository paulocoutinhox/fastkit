from fastkit_reports.contracts import ReportResult
from fastkit_reports.renderers.html import HtmlRenderer


class PdfRenderer:
    """Renders the HTML result to PDF through an injectable backend (e.g. WeasyPrint)."""

    name = "pdf"

    def __init__(self, backend):
        self._backend = backend
        self._html = HtmlRenderer()

    def render(self, result: ReportResult) -> bytes:
        html = self._html.render(result)

        return self._backend(html)
