from enums.report_chart_kind import ReportChartKind
from schemas.base_schema import BaseSchema
from schemas.report_series_schema import ReportSeriesSchema


class ReportPlotSchema(BaseSchema):
    key: str
    title: str
    kind: ReportChartKind
    labels: list[str]
    series: list[ReportSeriesSchema]
