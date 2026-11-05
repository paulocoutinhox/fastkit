from enum import StrEnum


class ReportChartKind(StrEnum):
    COLUMN = "column"
    BAR = "bar"
    LINE = "line"
    AREA = "area"
    PIE = "pie"
    DOUGHNUT = "doughnut"
