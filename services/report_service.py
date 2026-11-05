from dataclasses import replace

from sqlalchemy.ext.asyncio import AsyncSession

from enums.user import PANEL_ROLES
from helpers.bounded_pool import BoundedPool
from helpers.not_found_error import NotFoundError
from models.user import User
from reports.registry import REPORTS
from schemas.base_schema import BaseSchema
from services.report import Report
from services.report_document import ReportDocument
from services.report_exporter import ReportExporter
from services.tenant_service import tenant_service
from services.user_group_service import user_group_service

# A page or a sheet of thousands of rows holds a lot of memory while it is written, so a burst of exports waits for these threads.
EXPORTING_WORKERS = 2

exporting = BoundedPool(EXPORTING_WORKERS, "exporting")


class ReportService:
    """The reports an operator reaches, and what running one of them answers."""

    async def reachable(self, db: AsyncSession, operator: User) -> list[str]:
        """The codes of every report this account reaches, which is what the panel draws its menu out of."""
        if operator.role not in PANEL_ROLES:
            return []

        # The groups are read once for every report, because each rule asking on its own would be a query per report, and never where no report names one.
        named = frozenset().union(*(report.access.groups_named() for report in REPORTS.values()))
        groups = await user_group_service.codes_of(db, operator) if named else frozenset()

        return sorted(code for code, report in REPORTS.items() if report.access.permits(operator, groups))

    async def reached(self, db: AsyncSession, operator: User, code: str) -> Report:
        """The report this operator asked for, where one they do not reach is one that does not exist."""
        report = REPORTS.get(code)

        if report is None or not await report.access.admits(db, operator):
            raise NotFoundError()

        return report

    async def run(self, db: AsyncSession, report: Report, chosen: BaseSchema, operator: User) -> ReportDocument:
        rows = await report.rows(db, chosen, operator)
        brand = await tenant_service.brand_of(db, operator.tenant_id)

        document = report.document(rows, operator, brand)
        details = await report.details(db, chosen, operator, document)

        return replace(document, details=details)

    async def export(self, document: ReportDocument, exporter: ReportExporter) -> bytes:
        """The file, written on a thread of its own because drawing a page or a sheet of thousands of rows would hold every other request of the loop."""
        return await exporting.run(exporter.render, document)


report_service = ReportService()
