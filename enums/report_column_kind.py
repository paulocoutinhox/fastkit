from enum import StrEnum


class ReportColumnKind(StrEnum):
    TEXT = "text"
    INTEGER = "integer"
    MONEY = "money"
    DATE = "date"
    DATETIME = "datetime"
    ENUM = "enum"
