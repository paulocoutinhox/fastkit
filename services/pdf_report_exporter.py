from markupsafe import Markup
from weasyprint import HTML
from weasyprint.urls import URLFetcher

from helpers import templates
from services.report_document import ReportDocument
from services.report_exporter import ReportExporter
from services.report_figure import report_figure


class PdfReportExporter(ReportExporter):
    """A report as a printed page, drawn by WeasyPrint out of a template a tenant may override like any other, and a report may name a template of its own that extends the shared one."""

    code = "pdf"
    label = "report.format-pdf"
    media_type = "application/pdf"
    extension = "pdf"

    def __init__(self, template: str = "report/document.html"):
        self.template = template

    def render(self, document: ReportDocument) -> bytes:
        # The image is drawn here, from numbers and labels the vector writer escapes, so it is the one markup the page trusts.
        figures = [(plot, Markup(report_figure.svg(plot, document.locale))) for plot in document.plots]
        drawn = templates.render(self.template, document.brand_code, {"document": document, "figures": figures})

        # The page carries everything it draws, so any address inside it is something a row smuggled in, and fetching it would reach a file or a machine on the operator's behalf.
        sealed = URLFetcher(allowed_protocols=(), fail_on_errors=True)

        return HTML(string=drawn, url_fetcher=sealed).write_pdf()
