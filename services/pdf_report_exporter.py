from markupsafe import Markup
from weasyprint import HTML
from weasyprint.urls import URLFetcher

from enums.page_orientation import PageOrientation
from helpers import templates
from services.report_document import ReportDocument
from services.report_exporter import ReportExporter
from services.report_figure import report_figure


class PdfReportExporter(ReportExporter):
    """A report as a printed page, drawn by WeasyPrint out of a template a tenant may override like any other, where a report names the template it extends the shared one with and which way the page lies."""

    code = "pdf"
    label = "report.format-pdf"
    media_type = "application/pdf"
    extension = "pdf"

    def __init__(self, template: str = "report/document.html", orientation: PageOrientation = PageOrientation.LANDSCAPE):
        self.template = template
        self.orientation = orientation

    def render(self, document: ReportDocument) -> bytes:
        # The image is drawn here, from numbers and labels the vector writer escapes, so it is the one markup the page trusts.
        figures = [(plot, Markup(report_figure.svg(plot, document.locale))) for plot in document.plots]
        drawn = templates.render(self.template, document.brand_code, {"document": document, "figures": figures, "orientation": self.orientation})

        # The page carries everything it draws, so any address inside it is something a row smuggled in, and fetching it would reach a file or a machine on the operator's behalf.
        sealed = URLFetcher(allowed_protocols=(), fail_on_errors=True)

        return HTML(string=drawn, url_fetcher=sealed).write_pdf()
