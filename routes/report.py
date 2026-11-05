from typing import Annotated

from fastapi import APIRouter, Depends, Path, Request, Response
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError as SchemaError
from pydantic.alias_generators import to_camel

from enums.user import PANEL_ROLES
from helpers.auth import CurrentUser, requires
from helpers.dates import read_in
from helpers.db import DatabaseSession
from helpers.i18n import translate
from schemas.base_schema import BaseSchema
from schemas.report_column_schema import ReportColumnSchema
from schemas.report_format_schema import ReportFormatSchema
from schemas.report_plot_schema import ReportPlotSchema
from schemas.report_result_schema import ReportResultSchema
from schemas.report_schema import ReportSchema
from schemas.report_series_schema import ReportSeriesSchema
from services.report import Report
from services.report_document import ReportDocument
from services.report_service import report_service

# A report and a format are named by a segment of the address, which is written the way every other segment is.
Segment = Annotated[str, Path(max_length=64, pattern=r"^[a-z0-9-]+$")]

# The panel is where a report is read, so nobody outside it reaches one whatever the report itself would let in.
router = APIRouter(prefix="/reports", tags=["reports"], dependencies=[Depends(requires(*PANEL_ROLES))])


def chosen_by(report: Report, request: Request) -> BaseSchema:
    """The filter rides on the query string, read through the rules of the report so a value it cannot read or a name it does not know is refused like any other payload."""
    try:
        return report.filters.model_validate(dict(request.query_params))
    except SchemaError as refused:
        raise RequestValidationError(refused.errors()) from refused


def answered(document: ReportDocument) -> ReportResultSchema:
    columns = [ReportColumnSchema(key=to_camel(column.key), label=document.heading(column), kind=column.kind) for column in document.columns]
    rows = [{to_camel(column.key): document.shown(column, row) for column in document.columns} for row in document.rows]

    charts = [ReportPlotSchema(key=plot.key, title=plot.title, kind=plot.kind, labels=list(plot.labels), series=[ReportSeriesSchema(name=series.name, values=list(series.values), shown=list(series.shown)) for series in plot.series]) for plot in document.plots]

    return ReportResultSchema(columns=columns, rows=rows, count=len(rows), charts=charts, details=document.details)


@router.get("/{code}", response_model=ReportSchema, summary="Describe a report")
async def read_report(db: DatabaseSession, user: CurrentUser, code: Segment):
    """The title, the formats and the filter the screen of a report opens with, which is null where it waits for the operator to choose one."""
    report = await report_service.reached(db, user, code)
    opening = report.default_filter(user)
    formats = [ReportFormatSchema(code=exporter.code, label=translate(exporter.label)) for exporter in report.exporters]

    return ReportSchema(code=report.code, title=translate(report.title), formats=formats, default_filter=None if opening is None else opening.model_dump(mode="json", by_alias=True, exclude_none=True))


@router.get("/{code}/rows", response_model=ReportResultSchema, summary="Run a report")
async def read_rows(db: DatabaseSession, user: CurrentUser, request: Request, code: Segment):
    """The rows the filter on the query string selects, refused with `error.report-too-large` where they pass the most a report carries."""
    report = await report_service.reached(db, user, code)
    document = await report_service.run(db, report, chosen_by(report, request), user)

    return answered(document)


@router.get("/{code}/export/{format}", summary="Export a report", response_class=Response)
async def export_report(db: DatabaseSession, user: CurrentUser, request: Request, code: Segment, format: Segment):
    """The same rows as a file in one of the formats the report offers, named after the report and the moment it was written."""
    report = await report_service.reached(db, user, code)
    exporter = report.exporter(format)
    document = await report_service.run(db, report, chosen_by(report, request), user)
    content = await report_service.export(document, exporter)
    filename = f"{report.code}-{read_in(document.generated_at, document.zone, '%Y%m%d-%H%M')}.{exporter.extension}"

    return Response(content, media_type=exporter.media_type, headers={"Content-Disposition": f'attachment; filename="{filename}"'})
