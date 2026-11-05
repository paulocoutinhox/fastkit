from enums.report_column_kind import ReportColumnKind
from schemas.base_schema import BaseSchema


class ReportColumnSchema(BaseSchema):
    key: str
    label: str
    kind: ReportColumnKind
