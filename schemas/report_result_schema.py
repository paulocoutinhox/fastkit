from schemas.base_schema import BaseSchema
from schemas.report_column_schema import ReportColumnSchema
from schemas.report_plot_schema import ReportPlotSchema


class ReportResultSchema(BaseSchema):
    """What one run of a report answered, written the way the operator reads it: in their language, on their clock and in the currency of each amount."""

    columns: list[ReportColumnSchema]
    rows: list[dict[str, str | None]]
    count: int

    # The charts drawn above the rows, in the order the report declares them.
    charts: list[ReportPlotSchema]

    # Whatever else the report answers for a screen of its own, with its keys as the report wrote them.
    details: dict
