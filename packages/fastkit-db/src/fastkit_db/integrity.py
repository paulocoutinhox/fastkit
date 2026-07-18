import re
from dataclasses import dataclass

_UNIQUE_SQLITE = re.compile(
    r"UNIQUE constraint failed: (?P<columns>[^\n]+)", re.IGNORECASE
)
_NOT_NULL_SQLITE = re.compile(
    r"NOT NULL constraint failed: (?P<columns>[^\n]+)", re.IGNORECASE
)
_NOT_NULL_POSTGRES = re.compile(
    r'null value in column "(?P<column>[^"]+)"', re.IGNORECASE
)
_NOT_NULL_MYSQL = re.compile(
    r"Column ['`](?P<column>[^'`]+)['`] cannot be null", re.IGNORECASE
)
_POSTGRES_KEY = re.compile(r"Key \((?P<columns>[^)]+)\)=", re.IGNORECASE)
_MYSQL_FOREIGN_KEY = re.compile(
    r"FOREIGN KEY \([`\"']?(?P<columns>[^)]+?)[`\"']?\)", re.IGNORECASE
)
_CONSTRAINT = re.compile(
    r"constraint [\"'`](?P<constraint>[^\"'`]+)[\"'`]", re.IGNORECASE
)
_RELATION = re.compile(
    r'(?:table|relation) ["`\'](?P<table>[^"`\']+)["`\']', re.IGNORECASE
)
_MYSQL_UNIQUE = re.compile(
    r"Duplicate entry .+ for key ['`](?P<key>[^'`]+)['`]", re.IGNORECASE
)
_CHECK_SQLITE = re.compile(
    r"CHECK constraint failed(?:: (?P<constraint>[^\n]+))?", re.IGNORECASE
)


@dataclass(frozen=True)
class IntegrityViolation:
    kind: str
    columns: list[str]
    table: str | None = None
    constraint: str | None = None


def _identifiers(value: str) -> list[str]:
    return [part.strip().strip("`\"' ") for part in value.split(",")]


def _qualified_columns(match) -> tuple[list[str], str | None]:
    identifiers = _identifiers(match.group("columns"))
    columns = [identifier.rsplit(".", 1)[-1] for identifier in identifiers]
    tables = {
        identifier.rsplit(".", 1)[0] for identifier in identifiers if "." in identifier
    }

    return columns, tables.pop() if len(tables) == 1 else None


def _driver_metadata(original, text: str) -> tuple[str | None, str | None]:
    diagnostic = getattr(original, "diag", None)
    table = getattr(diagnostic, "table_name", None) if diagnostic is not None else None
    constraint = (
        getattr(diagnostic, "constraint_name", None) if diagnostic is not None else None
    )

    if table is None:
        match = _RELATION.search(text)
        table = match.group("table") if match else None

    if constraint is None:
        match = _CONSTRAINT.search(text)
        constraint = match.group("constraint") if match else None

    return table, constraint


def classify_integrity_error(error) -> IntegrityViolation:
    original = getattr(error, "orig", error)
    text = str(original)
    lowered = text.lower()
    table, constraint = _driver_metadata(original, text)

    if (
        "foreign key constraint failed" in lowered
        or "foreign key constraint" in lowered
    ):
        match = _POSTGRES_KEY.search(text) or _MYSQL_FOREIGN_KEY.search(text)
        columns = _qualified_columns(match)[0] if match else []

        return IntegrityViolation("foreign_key", columns, table, constraint)

    match = _UNIQUE_SQLITE.search(text)

    if match:
        columns, sqlite_table = _qualified_columns(match)

        return IntegrityViolation("unique", columns, table or sqlite_table, constraint)

    if (
        "unique constraint" in lowered
        or "duplicate key" in lowered
        or "duplicate entry" in lowered
    ):
        match = _POSTGRES_KEY.search(text)
        columns = _qualified_columns(match)[0] if match else []
        mysql_match = _MYSQL_UNIQUE.search(text)

        if mysql_match and constraint is None:
            key = mysql_match.group("key")
            key_parts = key.rsplit(".", 1)
            constraint = key_parts[-1]
            table = table or (key_parts[0] if len(key_parts) == 2 else None)

        return IntegrityViolation("unique", columns, table, constraint)

    match = _NOT_NULL_SQLITE.search(text)

    if match:
        columns, sqlite_table = _qualified_columns(match)

        return IntegrityViolation(
            "not_null", columns, table or sqlite_table, constraint
        )

    match = _NOT_NULL_POSTGRES.search(text) or _NOT_NULL_MYSQL.search(text)

    if match:
        return IntegrityViolation(
            "not_null", [match.group("column")], table, constraint
        )

    match = _CHECK_SQLITE.search(text)

    if match:
        return IntegrityViolation(
            "check", [], table, constraint or match.group("constraint")
        )

    if "check constraint" in lowered:
        return IntegrityViolation("check", [], table, constraint)

    return IntegrityViolation("unknown", [], table, constraint)
