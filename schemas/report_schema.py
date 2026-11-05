from schemas.base_schema import BaseSchema
from schemas.report_format_schema import ReportFormatSchema


class ReportSchema(BaseSchema):
    """What the screen of a report needs before it runs: its title, the formats it is taken away in, and the filter it opens applied, if any."""

    code: str
    title: str
    formats: list[ReportFormatSchema]
    default_filter: dict | None
