from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from enums.report_chart_kind import ReportChartKind
from enums.report_chart_period import ReportChartPeriod
from enums.report_column_kind import ReportColumnKind
from enums.subscription import ELIGIBLE_SUBSCRIPTION_STATUSES
from enums.user_role import UserRole
from helpers.i18n import translate
from models.integration import Integration
from models.plan import Plan
from models.subscription import Subscription
from models.user import User
from reports.subscriptions_excel_exporter import SubscriptionsExcelExporter
from schemas.subscriptions_filter import SubscriptionsFilter
from services.any_of import AnyOf
from services.csv_report_exporter import CsvReportExporter
from services.grouped_report_chart import GroupedReportChart
from services.has_role import HasRole
from services.in_group import InGroup
from services.pdf_report_exporter import PdfReportExporter
from services.report import Report
from services.report_column import ReportColumn
from services.report_document import ReportDocument


class SubscriptionsReport(Report):
    """Every subscription an account holds, by where it stands and the gateway it is paid through."""

    code = "subscriptions"
    title = "report.subscriptions"
    filters = SubscriptionsFilter
    columns = (
        ReportColumn("email", "report.column-email"),
        ReportColumn("plan", "report.column-plan"),
        ReportColumn("status", "report.column-status", ReportColumnKind.ENUM, enum_name="subscription_status"),
        ReportColumn("provider", "report.column-provider", ReportColumnKind.ENUM, enum_name="provider"),
        ReportColumn("started_at", "report.column-started-at", ReportColumnKind.DATETIME),
        ReportColumn("access_until", "report.column-access-until", ReportColumnKind.DATETIME),
    )

    # Whoever follows the revenue reads it too, which is a group an administrator puts them in and never a role of their own.
    access = AnyOf(HasRole(UserRole.ADMINISTRATOR), InGroup("finance"))

    charts = (
        GroupedReportChart("statuses", "report.chart-by-status", ReportChartKind.PIE, category="status"),
        GroupedReportChart("providers", "report.chart-by-provider", ReportChartKind.BAR, category="provider"),
        GroupedReportChart("started", "report.chart-started-per-month", ReportChartKind.LINE, category="started_at", period=ReportChartPeriod.MONTH),
    )

    # The figures the screen draws above the charts are drawn on the printed page and on a sheet of their own too, so each format says the same.
    exporters = (PdfReportExporter("report/subscriptions.html"), SubscriptionsExcelExporter(), CsvReportExporter())

    async def details(self, db: AsyncSession, chosen: SubscriptionsFilter, operator: User, document: ReportDocument) -> dict:
        accounts = {row["account"] for row in document.rows}
        eligible = [row for row in document.rows if row["status"] in ELIGIBLE_SUBSCRIPTION_STATUSES]
        figures = [
            {"key": "subscriptions", "label": translate("report.figure-subscriptions", document.locale), "value": len(document.rows)},
            {"key": "accounts", "label": translate("report.figure-accounts", document.locale), "value": len(accounts)},
            {"key": "eligible", "label": translate("report.figure-eligible", document.locale), "value": len(eligible)},
        ]

        return {"figures": figures}

    def statement(self, chosen: SubscriptionsFilter, operator: User):
        statement = select(User.id.label("account"), User.email.label("email"), Plan.name.label("plan"), Subscription.status.label("status"), Integration.provider.label("provider"), Subscription.started_at.label("started_at"), Subscription.access_until.label("access_until"))
        statement = statement.join(User, User.id == Subscription.user_id).join(Plan, Plan.id == Subscription.plan_id).outerjoin(Integration, Integration.id == Subscription.integration_id)

        if chosen.status is not None:
            statement = statement.where(Subscription.status == chosen.status)

        if chosen.provider is not None:
            statement = statement.where(Integration.provider == chosen.provider)

        if chosen.started_from is not None:
            statement = statement.where(Subscription.started_at >= self.midnight(chosen.started_from, operator))

        # The last day of the period is read until it ends, which is the start of the one after it.
        if chosen.started_until is not None:
            statement = statement.where(Subscription.started_at < self.midnight(chosen.started_until + timedelta(days=1), operator))

        return self.confined(statement, Subscription.tenant_id, operator).order_by(Subscription.id.desc())
