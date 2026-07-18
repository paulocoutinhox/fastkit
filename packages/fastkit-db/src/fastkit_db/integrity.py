import re
from dataclasses import dataclass

_UNIQUE = re.compile(r"UNIQUE constraint failed: (?P<columns>[^\n]+)")
_NOT_NULL_SQLITE = re.compile(r"NOT NULL constraint failed: (?P<columns>[^\n]+)")
_NOT_NULL_POSTGRES = re.compile(r'null value in column "(?P<column>[^"]+)"')
_POSTGRES_KEY = re.compile(r"Key \((?P<columns>[^)]+)\)=")


@dataclass(frozen=True)
class IntegrityViolation:
    kind: str
    columns: list[str]


def _columns(match) -> list[str]:
    return [part.strip().split(".")[-1] for part in match.group("columns").split(",")]


def classify_integrity_error(error) -> IntegrityViolation:
    """Classify a driver IntegrityError so a caller can point a form at the offending fields.

    `kind` is `unique`, `foreign_key`, `not_null`, `check` or `unknown`, and `columns` holds the
    conflicting column names when the driver reports them (SQLite names them for unique/not-null,
    PostgreSQL names them via `Key (...)`). SQLite does not name the column for a foreign-key or
    check violation, so `columns` is empty there and the caller degrades to a generic message.
    """

    text = str(getattr(error, "orig", error))

    if "FOREIGN KEY constraint failed" in text or "foreign key constraint" in text:
        match = _POSTGRES_KEY.search(text)

        return IntegrityViolation("foreign_key", _columns(match) if match else [])

    match = _UNIQUE.search(text)

    if match:
        return IntegrityViolation("unique", _columns(match))

    if "unique constraint" in text or "duplicate key" in text:
        match = _POSTGRES_KEY.search(text)

        return IntegrityViolation("unique", _columns(match) if match else [])

    match = _NOT_NULL_SQLITE.search(text)

    if match:
        return IntegrityViolation("not_null", _columns(match))

    match = _NOT_NULL_POSTGRES.search(text)

    if match:
        return IntegrityViolation("not_null", [match.group("column")])

    if "CHECK constraint failed" in text or "check constraint" in text:
        return IntegrityViolation("check", [])

    return IntegrityViolation("unknown", [])
