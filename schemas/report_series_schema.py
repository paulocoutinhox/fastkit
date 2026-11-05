from schemas.base_schema import BaseSchema


class ReportSeriesSchema(BaseSchema):
    name: str
    values: list[float]

    # Each value the way the operator reads it, which is what a tooltip says.
    shown: list[str]
