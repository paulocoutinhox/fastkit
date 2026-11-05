from datetime import timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select

from enums.report_chart_kind import ReportChartKind
from enums.report_column_kind import ReportColumnKind
from helpers.dates import now
from models.product import Product
from models.purchase import Purchase
from models.user import User
from schemas.purchases_filter import PurchasesFilter
from services.excel_report_exporter import ExcelReportExporter
from services.grouped_report_chart import GroupedReportChart
from services.pdf_report_exporter import PdfReportExporter
from services.report import Report
from services.report_column import ReportColumn

# The window the screen opens on, which is the month an operator usually asks about first.
OPENING_DAYS = 30


class PurchasesReport(Report):
    """Every purchase opened in a period, with who bought what, for how much and where it stands."""

    code = "purchases"
    title = "report.purchases"
    filters = PurchasesFilter
    columns = (
        ReportColumn("reference", "report.column-reference"),
        ReportColumn("created_at", "report.column-opened-at", ReportColumnKind.DATETIME),
        ReportColumn("email", "report.column-email"),
        ReportColumn("product", "report.column-product"),
        ReportColumn("status", "report.column-status", ReportColumnKind.ENUM, enum_name="purchase_status"),
        ReportColumn("price", "report.column-price", ReportColumnKind.MONEY, currency="currency"),
        ReportColumn("paid_at", "report.column-paid-at", ReportColumnKind.DATETIME),
    )
    charts = (GroupedReportChart("paid", "report.chart-paid-per-day", ReportChartKind.COLUMN, category="paid_at", value="price"), GroupedReportChart("statuses", "report.chart-by-status", ReportChartKind.DOUGHNUT, category="status"))
    exporters = (PdfReportExporter(), ExcelReportExporter())

    def default_filter(self, operator: User) -> PurchasesFilter:
        today = now().astimezone(ZoneInfo(operator.timezone)).date()

        return PurchasesFilter(starts_on=today - timedelta(days=OPENING_DAYS), ends_on=today)

    def statement(self, chosen: PurchasesFilter, operator: User):
        statement = select(Purchase.reference.label("reference"), Purchase.created_at.label("created_at"), User.email.label("email"), Product.name.label("product"), Purchase.status.label("status"), Purchase.price.label("price"), Purchase.currency.label("currency"), Purchase.paid_at.label("paid_at"))
        statement = statement.join(User, User.id == Purchase.user_id).join(Product, Product.id == Purchase.product_id)

        # A day is the one on the operator's clock, and the last day of the period is read until it ends, which is the start of the one after it.
        statement = statement.where(Purchase.created_at >= self.midnight(chosen.starts_on, operator), Purchase.created_at < self.midnight(chosen.ends_on + timedelta(days=1), operator))

        if chosen.status is not None:
            statement = statement.where(Purchase.status == chosen.status)

        return self.confined(statement, Purchase.tenant_id, operator).order_by(Purchase.created_at.desc(), Purchase.id.desc())
